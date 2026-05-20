from __future__ import annotations

import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
from openai import OpenAI

from hypergraphrag.openai_config import (
    ensure_openai_api_key,
    get_openai_base_url,
    get_openai_model,
)

DEFAULT_GENERATION_MODEL = os.getenv(
    "HGRAG_GENERATION_MODEL", get_openai_model(default="deepseek-chat")
)
DEFAULT_JUDGE_MODEL = os.getenv(
    "HGRAG_JUDGE_MODEL", get_openai_model(default="deepseek-chat")
)
SUPPORTED_BATCH_MODELS = {"deepseek-v3", "deepseek-r1", "deepseek-r1-32b"}
DEFAULT_BACKEND = os.getenv("HGRAG_INFERENCE_BACKEND", "realtime").strip().lower()
DEFAULT_BATCH_STAGING_DIR = Path(__file__).resolve().parent / "batch_jobs"


@dataclass(frozen=True)
class InferenceRequest:
    custom_id: str
    messages: list[dict[str, Any]]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResponse:
    custom_id: str
    content: str = ""
    error: Optional[str] = None
    raw: Optional[dict[str, Any]] = None
    usage: Optional[dict[str, Any]] = None


class BaseInferenceBackend:
    def run_requests(
        self,
        requests_: list[InferenceRequest],
        *,
        model: str,
        task_name: str,
        workers: int = 1,
    ) -> list[InferenceResponse]:
        raise NotImplementedError


class RealtimeInferenceBackend(BaseInferenceBackend):
    def __init__(self):
        api_key = ensure_openai_api_key()
        base_url = get_openai_base_url(default="https://api.deepseek.com")
        client_kwargs = {"api_key": api_key}
        client_kwargs["timeout"] = float(os.getenv("HGRAG_OPENAI_TIMEOUT_SECONDS", "180"))
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    def _run_one(self, request: InferenceRequest, model: str) -> InferenceResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": request.messages,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            response_dump = response.model_dump() if hasattr(response, "model_dump") else None
            usage = normalize_usage_payload(getattr(response, "usage", None))
            if usage is None and isinstance(response_dump, dict):
                usage = extract_usage_from_payload(response_dump)
            return InferenceResponse(
                custom_id=request.custom_id,
                content=content,
                raw=response_dump,
                usage=usage,
            )
        except Exception as exc:
            return InferenceResponse(
                custom_id=request.custom_id,
                error=str(exc),
            )

    def run_requests(
        self,
        requests_: list[InferenceRequest],
        *,
        model: str,
        task_name: str,
        workers: int = 1,
    ) -> list[InferenceResponse]:
        if not requests_:
            return []
        results_by_id: dict[str, InferenceResponse] = {}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_map = {
                executor.submit(self._run_one, request, model): request.custom_id
                for request in requests_
            }
            for future in as_completed(future_map):
                result = future.result()
                results_by_id[result.custom_id] = result
        return [results_by_id[request.custom_id] for request in requests_]


class QiniuBatchInferenceBackend(BaseInferenceBackend):
    def __init__(self):
        self.api_key = ensure_openai_api_key()
        self.base_url = get_openai_base_url(default="https://api.deepseek.com")
        if self.base_url and "api.deepseek.com" in self.base_url.rstrip("/"):
            raise RuntimeError(
                "DeepSeek official API does not expose the Qiniu batchjob endpoints used by this backend. "
                "Please use the realtime backend with DeepSeek official API."
            )
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        self.poll_interval = int(os.getenv("HGRAG_BATCH_POLL_INTERVAL_SECONDS", "30"))
        self.timeout_seconds = int(os.getenv("HGRAG_BATCH_TIMEOUT_SECONDS", str(12 * 3600)))
        self.staging_root = Path(
            os.getenv("HGRAG_BATCH_STAGING_DIR", str(DEFAULT_BATCH_STAGING_DIR))
        )
        self.public_root = os.getenv("HGRAG_BATCH_PUBLIC_ROOT")
        self.url_template = os.getenv("HGRAG_BATCH_INPUT_URL_TEMPLATE")

    def run_requests(
        self,
        requests_: list[InferenceRequest],
        *,
        model: str,
        task_name: str,
        workers: int = 1,
    ) -> list[InferenceResponse]:
        del workers  # Batch backend submits one job for the whole request set.
        if not requests_:
            return []
        if model not in SUPPORTED_BATCH_MODELS:
            raise RuntimeError(
                f"Batch backend only supports {sorted(SUPPORTED_BATCH_MODELS)}, got: {model}"
            )
        if not self.url_template:
            raise RuntimeError(
                "Batch backend requires HGRAG_BATCH_INPUT_URL_TEMPLATE, e.g. "
                "https://your-public-host/hgrag-batch/{task_name}/{filename}"
            )

        job_dir = self._prepare_job_dir(task_name)
        input_path = job_dir / "input.jsonl"
        self._write_input_jsonl(input_path, requests_)
        public_path = self._publish_input_file(job_dir, input_path)
        input_url = self._build_input_url(task_name=job_dir.name, input_path=public_path)
        job = self._create_job(model=model, task_name=job_dir.name, input_url=input_url)
        detail = self._wait_for_completion(job_id=job["id"])
        output_path = job_dir / "output.jsonl"
        self._download_output(detail["output_files_url"], output_path)
        parsed = self._parse_output_jsonl(output_path)
        responses = []
        for request in requests_:
            response = parsed.get(request.custom_id)
            if response is None:
                response = InferenceResponse(
                    custom_id=request.custom_id,
                    error="missing_response_in_batch_output",
                )
            responses.append(response)
        (job_dir / "job_detail.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return responses

    def _prepare_job_dir(self, task_name: str) -> Path:
        safe_name = slugify_task_name(task_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = self.staging_root / f"{timestamp}_{safe_name}"
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def _write_input_jsonl(self, input_path: Path, requests_: list[InferenceRequest]) -> None:
        with input_path.open("w", encoding="utf-8") as handle:
            for request in requests_:
                body: dict[str, Any] = {"messages": request.messages}
                if request.max_tokens is not None:
                    body["max_tokens"] = request.max_tokens
                if request.temperature is not None:
                    body["temperature"] = request.temperature
                if request.top_p is not None:
                    body["top_p"] = request.top_p
                payload = {"custom_id": request.custom_id, "body": body}
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _publish_input_file(self, job_dir: Path, input_path: Path) -> Path:
        if not self.public_root:
            return input_path
        public_root = Path(self.public_root)
        target_dir = public_root / job_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / input_path.name
        shutil.copy2(input_path, target_path)
        return target_path

    def _build_input_url(self, *, task_name: str, input_path: Path) -> str:
        return self.url_template.format(
            task_name=task_name,
            filename=input_path.name,
            relative_path=f"{task_name}/{input_path.name}",
        )

    def _create_job(self, *, model: str, task_name: str, input_url: str) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url.rstrip('/')}/batchjob/inference",
            json={
                "name": task_name,
                "model": model,
                "description": f"HyperGraphRAG evaluation batch job: {task_name}",
                "input_files_url": input_url,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _wait_for_completion(self, *, job_id: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        last_detail: Optional[dict[str, Any]] = None
        while time.time() < deadline:
            response = self.session.get(
                f"{self.base_url.rstrip('/')}/batchjob/inference/{job_id}", timeout=60
            )
            response.raise_for_status()
            detail = response.json()
            last_detail = detail
            status = detail.get("status")
            if status == "Completed":
                return detail
            if status in {"Failed", "Terminated"}:
                raise RuntimeError(
                    f"Batch job {job_id} ended with status={status}: {detail.get('status_message', '')}"
                )
            time.sleep(self.poll_interval)
        raise TimeoutError(f"Batch job {job_id} did not complete in time. Last detail: {last_detail}")

    def _download_output(self, output_url: str, output_path: Path) -> None:
        response = self.session.get(output_url, timeout=120)
        response.raise_for_status()
        output_path.write_text(response.text, encoding="utf-8")

    def _parse_output_jsonl(self, output_path: Path) -> dict[str, InferenceResponse]:
        results: dict[str, InferenceResponse] = {}
        with output_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                custom_id = payload.get("custom_id") or payload.get("id") or ""
                content, error, usage = extract_content_from_batch_payload(payload)
                results[custom_id] = InferenceResponse(
                    custom_id=custom_id,
                    content=content,
                    error=error,
                    raw=payload,
                    usage=usage,
                )
        return results


def slugify_task_name(task_name: str) -> str:
    task_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", task_name.strip())
    task_name = re.sub(r"-+", "-", task_name).strip("-")
    return task_name or "batch-task"


def make_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return make_jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return make_jsonable(value.dict())
    if isinstance(value, dict):
        return {str(key): make_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_jsonable(item) for item in value]
    return str(value)


def normalize_usage_payload(usage: Any) -> Optional[dict[str, Any]]:
    normalized = make_jsonable(usage)
    return normalized if isinstance(normalized, dict) else None


def extract_usage_from_payload(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    usage = normalize_usage_payload(payload.get("usage"))
    if usage is not None:
        return usage

    for key in ("response", "body", "result"):
        child = payload.get(key)
        if isinstance(child, dict):
            usage = extract_usage_from_payload(child)
            if usage is not None:
                return usage
    return None


def extract_text_from_response_body(body: dict[str, Any]) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(item.get("text", ""))
                    return "".join(parts)
    if isinstance(body.get("content"), str):
        return body["content"]
    if isinstance(body.get("output"), str):
        return body["output"]
    return ""


def extract_content_from_batch_payload(
    payload: dict[str, Any],
) -> tuple[str, Optional[str], Optional[dict[str, Any]]]:
    if not isinstance(payload, dict):
        return "", "invalid_batch_output_record", None

    usage = extract_usage_from_payload(payload)

    if payload.get("error"):
        if isinstance(payload["error"], dict):
            return (
                "",
                payload["error"].get("message") or json.dumps(payload["error"], ensure_ascii=False),
                usage,
            )
        return "", str(payload["error"]), usage

    response = payload.get("response")
    if isinstance(response, dict):
        if response.get("error"):
            err = response["error"]
            if isinstance(err, dict):
                return "", err.get("message") or json.dumps(err, ensure_ascii=False), usage
            return "", str(err), usage
        body = response.get("body")
        content = extract_text_from_response_body(body) if isinstance(body, dict) else ""
        if content:
            return content, None, usage

    body = payload.get("body")
    if isinstance(body, dict):
        content = extract_text_from_response_body(body)
        if content:
            return content, None, usage

    result = payload.get("result")
    if isinstance(result, dict):
        content = extract_text_from_response_body(result)
        if content:
            return content, None, usage
    if isinstance(result, str):
        return result, None, usage

    if isinstance(payload.get("content"), str):
        return payload["content"], None, usage

    return "", "unable_to_extract_batch_content", usage


def get_backend(kind: Optional[str] = None) -> BaseInferenceBackend:
    resolved = (kind or DEFAULT_BACKEND).strip().lower()
    if resolved == "realtime":
        return RealtimeInferenceBackend()
    if resolved == "batch":
        return QiniuBatchInferenceBackend()
    raise ValueError(f"Unsupported inference backend: {resolved}")


def get_generation_backend_kind() -> str:
    return os.getenv("HGRAG_GENERATION_BACKEND", DEFAULT_BACKEND).strip().lower()


def get_judge_backend_kind() -> str:
    return os.getenv("HGRAG_JUDGE_BACKEND", DEFAULT_BACKEND).strip().lower()


def get_generation_model() -> str:
    return os.getenv("HGRAG_GENERATION_MODEL", DEFAULT_GENERATION_MODEL).strip()


def get_judge_model() -> str:
    return os.getenv("HGRAG_JUDGE_MODEL", DEFAULT_JUDGE_MODEL).strip()


def get_generation_workers() -> int:
    return int(os.getenv("HGRAG_GENERATION_WORKERS", "2"))


def get_judge_workers() -> int:
    return int(os.getenv("HGRAG_SCORE_WORKERS", "1"))
