from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import traceback
from typing import Any

import pandas as pd
from graphrag.api import build_index
import graphrag.api.query as graphrag_query_api
from graphrag.cli.initialize import (
    BASIC_SEARCH_SYSTEM_PROMPT,
    COMMUNITY_REPORT_PROMPT,
    COMMUNITY_REPORT_TEXT_PROMPT,
    DRIFT_LOCAL_SYSTEM_PROMPT,
    DRIFT_REDUCE_PROMPT,
    EXTRACT_CLAIMS_PROMPT,
    GENERAL_KNOWLEDGE_INSTRUCTION,
    GRAPH_EXTRACTION_PROMPT,
    LOCAL_SEARCH_SYSTEM_PROMPT,
    MAP_SYSTEM_PROMPT,
    QUESTION_SYSTEM_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    SUMMARIZE_PROMPT,
)
from graphrag.config.load_config import load_config
from graphrag.data_model.data_reader import DataReader
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider
from openai import OpenAI

from hypergraphrag.openai_config import (
    DEFAULT_LOCAL_EMBED_MODEL,
    get_openai_api_key,
    get_openai_base_url,
    get_openai_embed_model,
    get_openai_model,
)


BASE_DIR = Path(__file__).resolve().parents[1]
OFFICIAL_GRAPHRAG_ROOT = BASE_DIR / "expr_official_graphrag"
DEFAULT_CREATION_DATE = "1970-01-01T00:00:00Z"
DEFAULT_OLLAMA_OPENAI_BASE = "http://127.0.0.1:11434/v1"

OLLAMA_EMBED_MODEL_ALIASES = {
    "qwen/qwen3-embedding-0.6b": "qwen3-embedding:0.6b",
    "qwen3-embedding-0.6b": "qwen3-embedding:0.6b",
    "qwen/qwen3-embedding-4b": "qwen3-embedding:4b",
    "qwen3-embedding-4b": "qwen3-embedding:4b",
    "qwen/qwen3-embedding-8b": "qwen3-embedding:8b",
    "qwen3-embedding-8b": "qwen3-embedding:8b",
}

PROMPT_FILES = {
    "extract_graph.txt": GRAPH_EXTRACTION_PROMPT,
    "summarize_descriptions.txt": SUMMARIZE_PROMPT,
    "extract_claims.txt": EXTRACT_CLAIMS_PROMPT,
    "community_report_graph.txt": COMMUNITY_REPORT_PROMPT,
    "community_report_text.txt": COMMUNITY_REPORT_TEXT_PROMPT,
    "drift_search_system_prompt.txt": DRIFT_LOCAL_SYSTEM_PROMPT,
    "drift_search_reduce_prompt.txt": DRIFT_REDUCE_PROMPT,
    "global_search_map_system_prompt.txt": MAP_SYSTEM_PROMPT,
    "global_search_reduce_system_prompt.txt": REDUCE_SYSTEM_PROMPT,
    "global_search_knowledge_system_prompt.txt": GENERAL_KNOWLEDGE_INSTRUCTION,
    "local_search_system_prompt.txt": LOCAL_SEARCH_SYSTEM_PROMPT,
    "basic_search_system_prompt.txt": BASIC_SEARCH_SYSTEM_PROMPT,
    "question_gen_system_prompt.txt": QUESTION_SYSTEM_PROMPT,
}

_COMMUNITY_REPORT_PATCH_APPLIED = False
_SUMMARY_CONTENT_FILTER_PATCH_APPLIED = False


@dataclass(frozen=True)
class OfficialGraphRAGModelConfig:
    chat_api_key: str
    chat_api_base: str
    chat_model: str
    embed_api_key: str
    embed_api_base: str
    embed_model: str
    embed_vector_size: int
    uses_local_embedding_service: bool


@dataclass
class OfficialGraphRAGLocalContextRunner:
    context_builder: Any
    context_builder_params: dict[str, Any]

    def build_context_records(self, query: str) -> dict[str, pd.DataFrame]:
        result = self.context_builder.build_context(
            query=query,
            **self.context_builder_params,
        )
        context_records = result.context_records
        if isinstance(context_records, dict):
            return context_records
        return {}


def resolve_graphrag_workspace(
    data_source: str,
    workspace_suffix: str | None = None,
) -> Path:
    workspace_name = data_source if not workspace_suffix else f"{data_source}_{workspace_suffix}"
    return OFFICIAL_GRAPHRAG_ROOT / workspace_name


def _normalize_embed_model_name(model_name: str) -> tuple[bool, str]:
    if model_name.startswith("local:"):
        resolved = model_name[len("local:") :].strip() or DEFAULT_LOCAL_EMBED_MODEL
        resolved = OLLAMA_EMBED_MODEL_ALIASES.get(resolved.lower(), resolved)
        return True, resolved
    return False, model_name


def _uses_deepseek_chat_stack(model_config: OfficialGraphRAGModelConfig) -> bool:
    chat_api_base = model_config.chat_api_base.lower()
    chat_model = model_config.chat_model.lower()
    return "deepseek" in chat_api_base or chat_model.startswith("deepseek")


def _llm_completion_uses_deepseek_json_mode_fallback(llm_completion: Any) -> bool:
    model_config = getattr(llm_completion, "_model_config", None)
    api_base = str(getattr(model_config, "api_base", "") or "").lower()
    model_name = str(getattr(model_config, "model", "") or "").lower()
    deployment_name = str(
        getattr(model_config, "azure_deployment_name", "") or ""
    ).lower()
    provider = str(getattr(model_config, "model_provider", "") or "").lower()
    model_identity = " ".join(
        part for part in (provider, model_name, deployment_name) if part
    )
    return "deepseek" in api_base or "deepseek" in model_identity


def _looks_like_content_filter_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "content management policy" in message
        or "content filter" in message
        or "response was filtered" in message
    )


def _fallback_description_summary(
    descriptions: list[str],
    *,
    max_summary_length: int,
) -> str:
    unique_descriptions = []
    seen = set()
    for description in descriptions:
        text = str(description).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_descriptions.append(text)

    combined = " ".join(unique_descriptions)
    max_chars = max(500, max_summary_length * 8)
    if len(combined) <= max_chars:
        return combined
    truncated = combined[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or combined[:max_chars].strip()


def ensure_summary_content_filter_patch() -> None:
    global _SUMMARY_CONTENT_FILTER_PATCH_APPLIED

    if _SUMMARY_CONTENT_FILTER_PATCH_APPLIED:
        return

    from graphrag.index.operations.summarize_descriptions import (
        description_summary_extractor as summary_module,
    )

    original_summarize = (
        summary_module.SummarizeExtractor._summarize_descriptions_with_llm
    )

    async def _patched_summarize_descriptions_with_llm(
        self,
        id: str | tuple[str, str] | list[str],
        descriptions: list[str],
    ):
        try:
            return await original_summarize(self, id, descriptions)
        except Exception as exc:
            if not _looks_like_content_filter_error(exc):
                raise
            self._on_error(
                exc,
                traceback.format_exc(),
                {
                    "id": id,
                    "fallback": "local_description_concat",
                    "description_count": len(descriptions),
                },
            )
            return _fallback_description_summary(
                descriptions,
                max_summary_length=self._max_summary_length,
            )

    summary_module.SummarizeExtractor._summarize_descriptions_with_llm = (
        _patched_summarize_descriptions_with_llm
    )
    _SUMMARY_CONTENT_FILTER_PATCH_APPLIED = True


def _extract_json_object_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise ValueError("DeepSeek community report response is empty.")

    if text.startswith("```"):
        fenced_lines = text.splitlines()
        if fenced_lines and fenced_lines[0].startswith("```"):
            fenced_lines = fenced_lines[1:]
        if fenced_lines and fenced_lines[-1].strip() == "```":
            fenced_lines = fenced_lines[:-1]
        text = "\n".join(fenced_lines).strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        candidate = text[start : end + 1].strip()
        json.loads(candidate)
        return candidate


def ensure_deepseek_community_report_patch() -> None:
    global _COMMUNITY_REPORT_PATCH_APPLIED

    if _COMMUNITY_REPORT_PATCH_APPLIED:
        return

    from graphrag.index.operations.summarize_communities import (
        community_reports_extractor as community_reports_module,
    )

    original_call = community_reports_module.CommunityReportsExtractor.__call__

    async def _patched_call(self, input_text: str):
        if not _llm_completion_uses_deepseek_json_mode_fallback(self._model):
            try:
                return await original_call(self, input_text)
            except Exception as e:
                if not _looks_like_content_filter_error(e):
                    raise
                community_reports_module.logger.exception(
                    "content filter while generating community report"
                )
                self._on_error(e, traceback.format_exc(), None)
                return community_reports_module.CommunityReportsResult(
                    structured_output=None,
                    output="",
                )

        output = None
        try:
            prompt = self._extraction_prompt.format(**{
                community_reports_module.INPUT_TEXT_KEY: input_text,
                community_reports_module.MAX_LENGTH_KEY: str(self._max_report_length),
            })
            response = await self._model.completion_async(
                messages=prompt,
                response_format_json_object=True,
            )
            response_text = _extract_json_object_text(response.content)
            output = community_reports_module.CommunityReportResponse.model_validate_json(
                response_text
            )
        except Exception as e:
            community_reports_module.logger.exception(
                "error generating community report"
            )
            self._on_error(e, traceback.format_exc(), None)

        text_output = self._get_text_output(output) if output else ""
        return community_reports_module.CommunityReportsResult(
            structured_output=output,
            output=text_output,
        )

    community_reports_module.CommunityReportsExtractor.__call__ = _patched_call
    _COMMUNITY_REPORT_PATCH_APPLIED = True


def resolve_official_model_config() -> OfficialGraphRAGModelConfig:
    chat_api_key = os.getenv("HGRAG_GRAPHRAG_CHAT_API_KEY") or get_openai_api_key()
    chat_api_base = os.getenv("HGRAG_GRAPHRAG_CHAT_API_BASE") or get_openai_base_url()
    chat_model = os.getenv("HGRAG_GRAPHRAG_CHAT_MODEL") or get_openai_model()

    requested_embed_model = (
        os.getenv("HGRAG_GRAPHRAG_EMBED_MODEL") or get_openai_embed_model()
    )
    uses_local_embedding_service, embed_model = _normalize_embed_model_name(
        requested_embed_model
    )

    if uses_local_embedding_service:
        embed_api_base = (
            os.getenv("HGRAG_GRAPHRAG_EMBED_API_BASE") or DEFAULT_OLLAMA_OPENAI_BASE
        )
        embed_api_key = os.getenv("HGRAG_GRAPHRAG_EMBED_API_KEY") or "ollama"
    else:
        embed_api_base = os.getenv("HGRAG_GRAPHRAG_EMBED_API_BASE") or chat_api_base
        embed_api_key = os.getenv("HGRAG_GRAPHRAG_EMBED_API_KEY") or chat_api_key

    configured_embed_vector_size = os.getenv("HGRAG_GRAPHRAG_EMBED_VECTOR_SIZE")
    if configured_embed_vector_size:
        embed_vector_size = int(configured_embed_vector_size)
    else:
        embed_client = OpenAI(api_key=embed_api_key, base_url=embed_api_base)
        embed_probe = embed_client.embeddings.create(
            model=embed_model,
            input=["vector size probe"],
        )
        embed_vector = embed_probe.data[0].embedding
        if not embed_vector:
            raise RuntimeError(
                f"Embedding probe returned an empty vector for model '{embed_model}'."
            )
        embed_vector_size = len(embed_vector)

    return OfficialGraphRAGModelConfig(
        chat_api_key=chat_api_key,
        chat_api_base=chat_api_base,
        chat_model=chat_model,
        embed_api_key=embed_api_key,
        embed_api_base=embed_api_base,
        embed_model=embed_model,
        embed_vector_size=embed_vector_size,
        uses_local_embedding_service=uses_local_embedding_service,
    )


def _render_settings_yaml(model_config: OfficialGraphRAGModelConfig) -> str:
    return f"""completion_models:
  default_completion_model:
    model_provider: openai
    model: {model_config.chat_model}
    auth_method: api_key
    api_key: ${{GRAPHRAG_CHAT_API_KEY}}
    api_base: "{model_config.chat_api_base}"
    retry:
      type: exponential_backoff

embedding_models:
  default_embedding_model:
    model_provider: openai
    model: {model_config.embed_model}
    auth_method: api_key
    api_key: ${{GRAPHRAG_EMBED_API_KEY}}
    api_base: "{model_config.embed_api_base}"
    retry:
      type: exponential_backoff

input:
  type: text

chunking:
  type: tokens
  size: 1200
  overlap: 100
  encoding_model: o200k_base

input_storage:
  type: file
  base_dir: "input"

output_storage:
  type: file
  base_dir: "output"

reporting:
  type: file
  base_dir: "logs"

cache:
  type: json
  storage:
    type: file
    base_dir: "cache"

vector_store:
  type: lancedb
  db_uri: output/lancedb
  vector_size: {model_config.embed_vector_size}

embed_text:
  embedding_model_id: default_embedding_model

extract_graph:
  completion_model_id: default_completion_model
  prompt: "prompts/extract_graph.txt"
  entity_types: [organization, person, geo, event]
  max_gleanings: 1

summarize_descriptions:
  completion_model_id: default_completion_model
  prompt: "prompts/summarize_descriptions.txt"
  max_length: 500

extract_graph_nlp:
  text_analyzer:
    extractor_type: regex_english

cluster_graph:
  max_cluster_size: 10

extract_claims:
  enabled: false
  completion_model_id: default_completion_model
  prompt: "prompts/extract_claims.txt"
  description: "Any claims or facts that could be relevant to information discovery."
  max_gleanings: 1

community_reports:
  completion_model_id: default_completion_model
  graph_prompt: "prompts/community_report_graph.txt"
  text_prompt: "prompts/community_report_text.txt"
  max_length: 2000
  max_input_length: 8000

snapshots:
  graphml: false
  embeddings: false

local_search:
  completion_model_id: default_completion_model
  embedding_model_id: default_embedding_model
  prompt: "prompts/local_search_system_prompt.txt"

global_search:
  completion_model_id: default_completion_model
  map_prompt: "prompts/global_search_map_system_prompt.txt"
  reduce_prompt: "prompts/global_search_reduce_system_prompt.txt"
  knowledge_prompt: "prompts/global_search_knowledge_system_prompt.txt"

drift_search:
  completion_model_id: default_completion_model
  embedding_model_id: default_embedding_model
  prompt: "prompts/drift_search_system_prompt.txt"
  reduce_prompt: "prompts/drift_search_reduce_prompt.txt"

basic_search:
  completion_model_id: default_completion_model
  embedding_model_id: default_embedding_model
  prompt: "prompts/basic_search_system_prompt.txt"
"""


def ensure_workspace_files(
    workspace: Path,
    *,
    model_config: OfficialGraphRAGModelConfig,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "input").mkdir(exist_ok=True)
    prompts_dir = workspace / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    for filename, content in PROMPT_FILES.items():
        prompt_path = prompts_dir / filename
        if not prompt_path.exists():
            prompt_path.write_text(content, encoding="utf-8")

    (workspace / "settings.yaml").write_text(
        _render_settings_yaml(model_config),
        encoding="utf-8",
    )
    (workspace / ".env").write_text(
        "\n".join(
            [
                f"GRAPHRAG_CHAT_API_KEY={model_config.chat_api_key}",
                f"GRAPHRAG_EMBED_API_KEY={model_config.embed_api_key}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _clear_workspace_dir(target: Path, workspace: Path) -> None:
    resolved_target = target.resolve()
    resolved_workspace = workspace.resolve()
    if resolved_target == resolved_workspace or resolved_workspace not in resolved_target.parents:
        raise RuntimeError(f"Refusing to remove unexpected path: {resolved_target}")
    if resolved_target.exists():
        shutil.rmtree(resolved_target)


def reset_workspace_artifacts(workspace: Path) -> None:
    for dirname in ("output", "cache", "logs"):
        target = workspace / dirname
        if target.exists():
            _clear_workspace_dir(target, workspace)


def _coerce_context_record(
    data_source: str,
    index: int,
    item: Any,
) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        title = f"{data_source}_{index:06d}"
        raw_data = {"source_index": index}
    elif isinstance(item, dict):
        text = str(
            item.get("text")
            or item.get("content")
            or item.get("page_content")
            or item.get("document")
            or ""
        ).strip()
        title = str(item.get("title") or item.get("id") or f"{data_source}_{index:06d}")
        raw_data = dict(item)
    else:
        raise TypeError(f"Unsupported context record type: {type(item)!r}")

    if not text:
        return None

    return {
        "id": f"{data_source}_{index:06d}",
        "text": text,
        "title": title,
        "creation_date": DEFAULT_CREATION_DATE,
        "raw_data": raw_data,
        "human_readable_id": index - 1,
    }


def load_input_documents_df(
    data_source: str,
    *,
    doc_limit: int | None = None,
) -> pd.DataFrame:
    context_path = BASE_DIR / "contexts" / f"{data_source}_contexts.json"
    with context_path.open(encoding="utf-8") as handle:
        raw_contexts = json.load(handle)

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw_contexts, start=1):
        record = _coerce_context_record(data_source, index, item)
        if record is not None:
            rows.append(record)
        if doc_limit is not None and len(rows) >= doc_limit:
            break

    if not rows:
        raise RuntimeError(f"No non-empty contexts found for dataset '{data_source}'.")

    return pd.DataFrame(rows)


def write_input_snapshot(workspace: Path, input_documents: pd.DataFrame) -> Path:
    snapshot_path = workspace / "input" / "documents.json"
    records = input_documents.to_dict(orient="records")
    snapshot_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return snapshot_path


def build_official_graphrag_index(
    data_source: str,
    *,
    doc_limit: int | None = None,
    workspace_suffix: str | None = None,
    force_rebuild: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    workspace = resolve_graphrag_workspace(data_source, workspace_suffix)
    model_config = resolve_official_model_config()
    ensure_summary_content_filter_patch()
    ensure_deepseek_community_report_patch()
    if force_rebuild:
        reset_workspace_artifacts(workspace)
    ensure_workspace_files(workspace, model_config=model_config)

    input_documents = load_input_documents_df(data_source, doc_limit=doc_limit)
    input_snapshot_path = write_input_snapshot(workspace, input_documents)
    config = load_config(workspace)
    pipeline_results = asyncio.run(
        build_index(
            config,
            method="standard",
            verbose=verbose,
            input_documents=input_documents,
        )
    )

    return {
        "workspace": workspace,
        "documents": len(input_documents),
        "input_snapshot_path": input_snapshot_path,
        "model_config": model_config,
        "pipeline_results": pipeline_results,
    }


def load_index_output_tables(workspace: Path) -> dict[str, pd.DataFrame | None]:
    config = load_config(workspace)
    storage_obj = create_storage(config.output_storage)
    table_provider = create_table_provider(config.table_provider, storage=storage_obj)
    reader = DataReader(table_provider)

    output_names = [
        "entities",
        "communities",
        "community_reports",
        "text_units",
        "relationships",
    ]
    optional_output_names = ["covariates"]
    dataframes: dict[str, pd.DataFrame | None] = {}

    for name in output_names:
        dataframes[name] = asyncio.run(getattr(reader, name)())
    for name in optional_output_names:
        if asyncio.run(table_provider.has(name)):
            dataframes[name] = asyncio.run(getattr(reader, name)())
        else:
            dataframes[name] = None
    return dataframes


def build_local_context_runner(
    data_source: str,
    *,
    workspace_suffix: str | None = None,
    community_level: int | None = None,
) -> OfficialGraphRAGLocalContextRunner:
    workspace = resolve_graphrag_workspace(data_source, workspace_suffix)
    config = load_config(workspace)
    output_tables = load_index_output_tables(workspace)
    resolved_community_level = (
        community_level
        if community_level is not None
        else int(os.getenv("HGRAG_GRAPHRAG_COMMUNITY_LEVEL", "2"))
    )

    description_embedding_store = graphrag_query_api.get_embedding_store(
        config=config.vector_store,
        embedding_name=graphrag_query_api.entity_description_embedding,
    )
    entities = graphrag_query_api.read_indexer_entities(
        output_tables["entities"],
        output_tables["communities"],
        resolved_community_level,
    )
    reports = graphrag_query_api.read_indexer_reports(
        output_tables["community_reports"],
        output_tables["communities"],
        resolved_community_level,
    )
    text_units = graphrag_query_api.read_indexer_text_units(output_tables["text_units"])
    relationships = graphrag_query_api.read_indexer_relationships(
        output_tables["relationships"]
    )
    covariates = (
        graphrag_query_api.read_indexer_covariates(output_tables["covariates"])
        if output_tables["covariates"] is not None
        else []
    )
    prompt = graphrag_query_api.load_search_prompt(config.local_search.prompt)

    search_engine = graphrag_query_api.get_local_search_engine(
        config=config,
        reports=reports,
        text_units=text_units,
        entities=entities,
        relationships=relationships,
        covariates={"claims": covariates},
        response_type=os.getenv(
            "HGRAG_GRAPHRAG_RESPONSE_TYPE",
            "multiple paragraphs",
        ),
        description_embedding_store=description_embedding_store,
        system_prompt=prompt,
    )
    return OfficialGraphRAGLocalContextRunner(
        context_builder=search_engine.context_builder,
        context_builder_params=dict(search_engine.context_builder_params),
    )


def _normalize_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value)


def _dataframe_to_csv_text(dataframe: pd.DataFrame) -> str:
    normalized = dataframe.copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].map(_normalize_csv_cell)
    return normalized.to_csv(index=False, lineterminator="\n")


def format_local_context_records(context_records: dict[str, Any]) -> str:
    sections: list[str] = []
    include_reports = os.getenv("HGRAG_GRAPHRAG_INCLUDE_REPORTS", "").lower() in {
        "1",
        "true",
        "yes",
    }
    section_order = [
        ("entities", "Entities"),
        ("relationships", "Relationships"),
        ("sources", "Sources"),
    ]
    if include_reports:
        section_order.insert(2, ("reports", "Reports"))

    for key, title in section_order:
        dataframe = context_records.get(key)
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            continue
        csv_text = _dataframe_to_csv_text(dataframe)
        sections.append(f"\n-----{title}-----\n```csv\n{csv_text}```\n")

    return "".join(sections).strip()
