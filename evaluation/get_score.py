import argparse
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from eval import cal_em, cal_f1
from eval_g import (
    GEN_METRICS,
    aggregate_metric_results,
    build_metric_prompt,
    parse_metric_response,
)
from eval_r import cal_rsim
from inference_backend import (
    InferenceRequest,
    get_backend,
    get_judge_backend_kind,
    get_judge_model,
    get_judge_workers,
)

score_workers = int(os.getenv("HGRAG_SCORE_WORKERS", "1"))


def parse_bool(value: str | bool | None, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def resolve_enable_llm_judge(cli_value: str | None) -> bool:
    if cli_value is not None:
        return parse_bool(cli_value, default=True)
    env_value = os.getenv("HGRAG_ENABLE_LLM_JUDGE")
    return parse_bool(env_value, default=True)


def extract_answer(generation: str) -> str:
    try:
        return generation.split("<answer>")[1].split("</answer>")[0].strip()
    except Exception:
        return generation


def normalize_token_count(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def normalize_sample_token_fields(sample: dict) -> None:
    for field in ("consumed_prompt_tokens", "consumed_completion_tokens", "consumed_total_tokens"):
        sample[field] = normalize_token_count(sample.get(field))


def compute_token_usage_summary(data: list[dict]) -> dict:
    consumed_tokens = []
    for sample in data:
        normalize_sample_token_fields(sample)
        total_tokens = sample.get("consumed_total_tokens")
        if total_tokens is not None:
            consumed_tokens.append(total_tokens)
    return {
        "avg_consumed_tokens": round(sum(consumed_tokens) / len(consumed_tokens), 4)
        if consumed_tokens
        else None,
        "token_usage_recorded_samples": len(consumed_tokens),
        "token_usage_total_samples": len(data),
    }


def make_json_serializable(value):
    if isinstance(value, dict):
        return {key: make_json_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_serializable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return value


def evaluate_local_metrics(sample: dict) -> dict:
    generation = sample['generation']
    answer = extract_answer(generation)
    em_score = cal_em([sample['golden_answers']], [answer])
    f1_score = cal_f1([sample['golden_answers']], [answer])

    context = []
    for chunk in sample['context']:
        if chunk not in context:
            context.append(chunk)

    rsim_score = cal_rsim(['\n'.join(context)], [sample['knowledge']]) if sample['knowledge'] != "" else 0.0
    sample['em'] = em_score
    sample['f1'] = f1_score
    sample['rsim'] = rsim_score
    return sample


def build_judge_requests(method: str, data_source: str, data: list[dict]) -> list[InferenceRequest]:
    requests = []
    for idx, sample in enumerate(data):
        for metric in GEN_METRICS:
            prompt = build_metric_prompt(metric, sample['question'], sample['golden_answers'], sample['generation'])
            requests.append(
                InferenceRequest(
                    custom_id=f"judge-{method}-{data_source}-{idx}-{metric}",
                    messages=[{"role": "user", "content": prompt}],
                )
            )
    return requests


def apply_judge_results(method: str, data_source: str, data: list[dict], responses) -> None:
    response_map = {response.custom_id: response for response in responses}
    for idx, sample in enumerate(data):
        metric_results = {}
        for metric in GEN_METRICS:
            custom_id = f"judge-{method}-{data_source}-{idx}-{metric}"
            response = response_map.get(custom_id)
            if response is None or response.error:
                content = ""
                if response is not None and response.error:
                    content = f"<score>5</score><explanation>Judge backend error: {response.error}</explanation>"
            else:
                content = response.content
            metric_results[metric] = parse_metric_response(content, sample['f1'])
        gen_score = aggregate_metric_results(metric_results)
        sample['gen'] = gen_score['score']
        sample['gen_exp'] = gen_score['explanation']


def apply_skipped_judge_results(data: list[dict]) -> None:
    for sample in data:
        sample['gen'] = None
        sample['gen_exp'] = None


def evaluate_method(args):
    method = args.method
    data_source = args.data_source
    enable_llm_judge = resolve_enable_llm_judge(args.enable_llm_judge)
    success_flag = False

    try:
        print(f"[DEBUG] Evaluating {method} on {data_source}")
        if enable_llm_judge:
            judge_backend_kind = get_judge_backend_kind()
            judge_backend = get_backend(judge_backend_kind)
            judge_model = get_judge_model()
            judge_workers = get_judge_workers()
            print(f"[DEBUG] judge backend={judge_backend_kind} model={judge_model} workers={judge_workers}")
        else:
            judge_backend_kind = None
            judge_backend = None
            judge_model = None
            judge_workers = 0
            print("[DEBUG] llm judge disabled; Gen metric will be skipped")
        data_dir = f"results/{method}/{data_source}/test_generation.json"
        if not os.path.exists(data_dir):
            raise FileNotFoundError(f"File not found: {data_dir}")

        with open(data_dir, encoding="utf-8") as f:
            data = json.load(f)

        if score_workers <= 1:
            data = [evaluate_local_metrics(sample) for sample in tqdm(data, desc=f"{method}-local")]
        else:
            with ThreadPoolExecutor(max_workers=score_workers) as executor:
                data = list(tqdm(executor.map(evaluate_local_metrics, data), total=len(data), desc=f"{method}-local"))

        if enable_llm_judge:
            judge_requests = build_judge_requests(method, data_source, data)
            judge_responses = judge_backend.run_requests(
                judge_requests,
                model=judge_model,
                task_name=f"judge-{method}-{data_source}",
                workers=judge_workers,
            )
            apply_judge_results(method, data_source, data, judge_responses)
        else:
            apply_skipped_judge_results(data)

        token_usage_summary = compute_token_usage_summary(data)
        overall_em = sum([sample['em'] for sample in data]) / len(data)
        overall_f1 = sum([sample['f1'] for sample in data]) / len(data)
        overall_rsim = sum([sample['rsim'] for sample in data]) / len(data)
        overall_gen = (
            sum([sample['gen'] for sample in data if sample.get('gen') is not None])
            / len([sample for sample in data if sample.get('gen') is not None])
            if enable_llm_judge
            else None
        )

        print(f"{method} Overall EM: {overall_em:.4f}")
        print(f"{method} Overall F1: {overall_f1:.4f}")
        print(f"{method} Overall R-Sim: {overall_rsim:.4f}")
        if overall_gen is None:
            print(f"{method} Overall Gen: skipped")
        else:
            print(f"{method} Overall Gen: {overall_gen:.4f}")
        if token_usage_summary["avg_consumed_tokens"] is None:
            print(f"{method} Avg Consumed Tokens: unavailable")
        else:
            print(f"{method} Avg Consumed Tokens: {token_usage_summary['avg_consumed_tokens']:.4f}")

        save_base = f"results/{method}/{data_source}"
        os.makedirs(save_base, exist_ok=True)

        result_path = os.path.join(save_base, "test_result.json")
        with open(result_path, 'w', encoding="utf-8") as f:
            json.dump(make_json_serializable(data), f, indent=4, ensure_ascii=False)

        score_path = os.path.join(save_base, "test_score.json")
        with open(score_path, 'w', encoding="utf-8") as f:
            json.dump(
                make_json_serializable({
                    "overall_em": overall_em,
                    "overall_f1": overall_f1,
                    "overall_rsim": overall_rsim,
                    "overall_gen": overall_gen,
                    "llm_judge_enabled": enable_llm_judge,
                    "judge_backend": judge_backend_kind,
                    "judge_model": judge_model,
                    "avg_consumed_tokens": token_usage_summary["avg_consumed_tokens"],
                    "token_usage_recorded_samples": token_usage_summary["token_usage_recorded_samples"],
                    "token_usage_total_samples": token_usage_summary["token_usage_total_samples"],
                }),
                f,
                indent=4,
                ensure_ascii=False,
            )

        success_flag = True
        print(f"[SAVED] {result_path}")
        print(f"[SAVED] {score_path}")
        print(f"[SUCCESS] {method} finished and saved.")
    except Exception as exc:
        print(f"\n[ERROR] {method} failed due to: {str(exc)}")
        traceback.print_exc()
        raise

    if not success_flag:
        raise RuntimeError(f"{method} did not complete saving.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', type=str, default='HyperGraphRAG_wo_ER')
    parser.add_argument('--data_source', type=str, default='hypertension')
    parser.add_argument(
        '--enable_llm_judge',
        type=str,
        default=None,
        help='Whether to compute Gen via LLM judge. Accepts true/false. '
             'Can also be set via HGRAG_ENABLE_LLM_JUDGE.',
    )
    evaluate_method(parser.parse_args())
