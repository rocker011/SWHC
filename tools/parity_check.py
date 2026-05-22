from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime
from typing import Any


DEFAULT_QUERY = "Were Scott Derrickson and Ed Wood of the same nationality?"
DEFAULT_LOW_KEYWORDS = "SCOTT DERRICKSON, ED WOOD, AMERICAN"
DEFAULT_HIGH_KEYWORDS = "<hyperedge>SCOTT DERRICKSON ED WOOD NATIONALITY"

CORE_FILES = [
    "evaluation/hypergraphrag/base.py",
    "evaluation/hypergraphrag/swhc.py",
    "evaluation/hypergraphrag/operate.py",
    "evaluation/methods/common.py",
    "evaluation/methods/swhc.py",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _copytree_clean(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _run_python(
    python: str,
    script: Path,
    *,
    cwd: Path,
    args: list[str],
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["PYTHONIOENCODING"] = "utf-8"
    run_env["HGRAG_QUERY_CONCURRENCY"] = "1"
    run_env["HGRAG_SWHC_SOURCE_RERANK"] = "false"
    run_env["HGRAG_OPENAI_TIMEOUT_SECONDS"] = run_env.get("HGRAG_OPENAI_TIMEOUT_SECONDS", "180")
    if env:
        run_env.update(env)
    return subprocess.run(
        [python, str(script), *args],
        cwd=str(cwd),
        env=run_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _child_script(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            r'''
            from __future__ import annotations

            import argparse
            import asyncio
            import json
            import os
            from pathlib import Path
            import sys

            sys.path.insert(0, os.getcwd())


            class TinyGraphStorage:
                def __init__(self):
                    self.nodes = {
                        "E1": {
                            "role": "entity",
                            "entity_type": "PERSON",
                            "description": "Scott Derrickson is an American filmmaker.",
                            "source_id": "c1",
                        },
                        "E2": {
                            "role": "entity",
                            "entity_type": "COUNTRY",
                            "description": "American nationality.",
                            "source_id": "c1",
                        },
                        "E3": {
                            "role": "entity",
                            "entity_type": "PERSON",
                            "description": "Ed Wood was an American filmmaker.",
                            "source_id": "c2",
                        },
                        "H1": {"role": "hyperedge", "weight": 4.0, "source_id": "c1"},
                        "H2": {"role": "hyperedge", "weight": 4.0, "source_id": "c2"},
                    }
                    self.edges = {
                        frozenset(("E1", "H1")): {"weight": 4.0, "source_id": "c1"},
                        frozenset(("E2", "H1")): {"weight": 4.0, "source_id": "c1"},
                        frozenset(("E2", "H2")): {"weight": 4.0, "source_id": "c2"},
                        frozenset(("E3", "H2")): {"weight": 4.0, "source_id": "c2"},
                    }

                async def get_node(self, node_id):
                    return self.nodes.get(node_id)

                async def get_edge(self, left, right):
                    return self.edges.get(frozenset((left, right)))

                async def get_node_edges(self, node_id):
                    return [
                        tuple(edge)
                        for edge in (tuple(key) for key in self.edges)
                        if node_id in edge
                    ]


            class TinyChunkStorage:
                def __init__(self):
                    self.chunks = {
                        "c1": {
                            "content": "Scott Derrickson is an American filmmaker.",
                            "chunk_order_index": 0,
                        },
                        "c2": {
                            "content": "Ed Wood was an American filmmaker.",
                            "chunk_order_index": 1,
                        },
                    }

                async def get_by_id(self, chunk_id):
                    return self.chunks.get(chunk_id)


            def _graph_payload(result, entities, relationships, sources):
                return {
                    "nodes": sorted(result.subgraph.nodes()),
                    "edges": sorted(sorted(edge) for edge in result.subgraph.edges()),
                    "debug": result.debug,
                    "entities": entities,
                    "relationships": relationships,
                    "sources": sources,
                }


            async def run_solver(output: Path):
                from hypergraphrag import QueryParam
                from hypergraphrag.swhc import format_swhc_context, solve_swhc

                params = QueryParam(
                    only_need_context=True,
                    subgraph_selector="swhc",
                    swhc_candidate_hops=2,
                    swhc_seed_topk_entity=2,
                    swhc_seed_topk_hyperedge=2,
                    swhc_hard_terminal_topk=3,
                    swhc_budget_nodes=8,
                )
                graph = TinyGraphStorage()
                chunks = TinyChunkStorage()
                result = await solve_swhc(
                    graph,
                    chunks,
                    entity_seeds=[
                        {"node_id": "E1", "seed_score": 1.0},
                        {"node_id": "E3", "seed_score": 0.9},
                    ],
                    hyperedge_seeds=[{"node_id": "H1", "seed_score": 0.8}],
                    query_param=params,
                    tiktoken_model_name="gpt-4o",
                )
                entities, relationships, sources = await format_swhc_context(
                    result,
                    chunks,
                    params,
                    query_text="Were Scott Derrickson and Ed Wood American?",
                )
                output.write_text(
                    json.dumps(
                        _graph_payload(result, entities, relationships, sources),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )


            async def run_context(data_source: str, query: str, low: str, high: str, output: Path):
                from hypergraphrag import HyperGraphRAG, QueryParam
                from hypergraphrag.operate import _build_query_context

                rag = HyperGraphRAG(
                    working_dir=f"expr/{data_source}",
                    embedding_func_max_async=1,
                    llm_model_max_async=1,
                )
                params = QueryParam(
                    only_need_context=True,
                    subgraph_selector="swhc",
                    swhc_source_rerank=False,
                )
                context = await _build_query_context(
                    [low, high],
                    rag.chunk_entity_relation_graph,
                    rag.entities_vdb,
                    rag.hyperedges_vdb,
                    rag.text_chunks,
                    params,
                    original_query=query,
                )
                output.write_text(
                    json.dumps({"query": query, "low": low, "high": high, "context": context}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )


            def main():
                parser = argparse.ArgumentParser()
                parser.add_argument("--mode", choices=["solver", "context"], required=True)
                parser.add_argument("--data-source")
                parser.add_argument("--query")
                parser.add_argument("--low")
                parser.add_argument("--high")
                parser.add_argument("--output", required=True)
                args = parser.parse_args()

                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                if args.mode == "solver":
                    asyncio.run(run_solver(output))
                else:
                    asyncio.run(run_context(args.data_source, args.query, args.low, args.high, output))


            if __name__ == "__main__":
                main()
            '''
        ).lstrip(),
        encoding="utf-8",
    )


def compare_core_files(old_root: Path, new_root: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in CORE_FILES:
        old_path = old_root / rel
        new_path = new_root / rel
        old_hash = _sha256(old_path) if old_path.exists() else None
        new_hash = _sha256(new_path) if new_path.exists() else None
        rows.append(
            {
                "path": rel,
                "old_exists": old_path.exists(),
                "new_exists": new_path.exists(),
                "old_sha256": old_hash,
                "new_sha256": new_hash,
                "equal": old_hash == new_hash and old_hash is not None,
            }
        )
    return rows


def load_env_mapping(env_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not env_path.exists():
        return mapping
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        mapping[key.strip()] = value.strip().strip('"').strip("'")
    return mapping


def write_old_api_config_from_env(old_root: Path, env_values: dict[str, str]) -> bytes | None:
    config_path = old_root / "api_config.txt"
    original = config_path.read_bytes() if config_path.exists() else None
    api_key = env_values.get("OPENAI_API_KEY") or env_values.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or DEEPSEEK_API_KEY is missing from .env")
    lines = [
        api_key,
        env_values.get("OPENAI_BASE_URL", "https://api.deepseek.com"),
        env_values.get("OPENAI_MODEL", "deepseek-v4-flash"),
        env_values.get("OPENAI_EMBED_MODEL", "local:Qwen/Qwen3-Embedding-0.6B"),
        "",
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return original


def restore_file(path: Path, original: bytes | None) -> None:
    if original is None:
        if path.exists():
            path.unlink()
    else:
        path.write_bytes(original)


def run_child_checks(
    python: str,
    old_root: Path,
    new_root: Path,
    dataset: str,
    parity_dataset: str,
    report_dir: Path,
    query: str,
    low: str,
    high: str,
) -> dict[str, Any]:
    old_eval = old_root / "evaluation"
    new_eval = new_root / "evaluation"
    old_expr = old_eval / "expr" / dataset
    new_parity_expr = new_eval / "expr" / parity_dataset
    _copytree_clean(old_expr, new_parity_expr)

    with tempfile.TemporaryDirectory(prefix="swhc_parity_") as tmp:
        child = Path(tmp) / "parity_child.py"
        _child_script(child)

        outputs = {
            "old_solver": report_dir / "old_solver.json",
            "new_solver": report_dir / "new_solver.json",
            "old_context": report_dir / "old_context.json",
            "new_context": report_dir / "new_context.json",
        }
        runs = {
            "old_solver": _run_python(
                python,
                child,
                cwd=old_eval,
                args=["--mode", "solver", "--output", str(outputs["old_solver"])],
            ),
            "new_solver": _run_python(
                python,
                child,
                cwd=new_eval,
                args=["--mode", "solver", "--output", str(outputs["new_solver"])],
            ),
            "old_context": _run_python(
                python,
                child,
                cwd=old_eval,
                args=[
                    "--mode",
                    "context",
                    "--data-source",
                    dataset,
                    "--query",
                    query,
                    "--low",
                    low,
                    "--high",
                    high,
                    "--output",
                    str(outputs["old_context"]),
                ],
            ),
            "new_context": _run_python(
                python,
                child,
                cwd=new_eval,
                args=[
                    "--mode",
                    "context",
                    "--data-source",
                    parity_dataset,
                    "--query",
                    query,
                    "--low",
                    low,
                    "--high",
                    high,
                    "--output",
                    str(outputs["new_context"]),
                ],
            ),
        }

    run_rows = {
        name: {
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
        }
        for name, proc in runs.items()
    }
    for name, proc in runs.items():
        if proc.returncode != 0:
            return {
                "runs": run_rows,
                "solver_equal": False,
                "context_equal": False,
                "error": f"{name} failed",
            }

    old_solver = _read_json(outputs["old_solver"])
    new_solver = _read_json(outputs["new_solver"])
    old_context = _read_json(outputs["old_context"])
    new_context = _read_json(outputs["new_context"])

    return {
        "runs": run_rows,
        "solver_equal": old_solver == new_solver,
        "context_equal": old_context == new_context,
        "old_solver_sha256": _sha256(outputs["old_solver"]),
        "new_solver_sha256": _sha256(outputs["new_solver"]),
        "old_context_sha256": _sha256(outputs["old_context"]),
        "new_context_sha256": _sha256(outputs["new_context"]),
        "context_length": len(old_context.get("context", "")),
    }


def run_e2e_cache_replay(
    python: str,
    old_root: Path,
    new_root: Path,
    dataset: str,
    parity_dataset: str,
    report_dir: Path,
    env_values: dict[str, str],
) -> dict[str, Any]:
    old_eval = old_root / "evaluation"
    new_eval = new_root / "evaluation"
    old_expr = old_eval / "expr" / dataset
    new_expr = new_eval / "expr" / parity_dataset
    old_dataset = old_eval / "datasets" / dataset
    new_dataset = new_eval / "datasets" / parity_dataset
    old_result = old_eval / "results" / "SWHC" / dataset / "test_knowledge.json"
    new_result = new_eval / "results" / "SWHC" / parity_dataset / "test_knowledge.json"
    old_cache = old_expr / "kv_store_llm_response_cache.json"

    old_api_config = old_root / "api_config.txt"
    old_api_original = write_old_api_config_from_env(old_root, env_values)
    old_cache_original = old_cache.read_bytes() if old_cache.exists() else None
    old_result_original = old_result.read_bytes() if old_result.exists() else None

    try:
        if old_cache.exists():
            old_cache.write_text("{}", encoding="utf-8")
        old_run = _run_python(
            python,
            old_eval / "script_swhc.py",
            cwd=old_eval,
            args=["--data_source", dataset],
        )
        if old_run.returncode != 0:
            return {
                "old_returncode": old_run.returncode,
                "old_stdout_tail": old_run.stdout[-4000:],
                "new_returncode": None,
                "equal": False,
                "error": "old e2e run failed",
            }

        _copytree_clean(old_expr, new_expr)
        _copytree_clean(old_dataset, new_dataset)
        new_run = _run_python(
            python,
            new_eval / "script_swhc.py",
            cwd=new_eval,
            args=["--data_source", parity_dataset],
            env=env_values,
        )
        if old_result.exists():
            shutil.copy2(old_result, report_dir / "old_e2e_test_knowledge.json")
        if new_result.exists():
            shutil.copy2(new_result, report_dir / "new_e2e_test_knowledge.json")

        equal = False
        if old_result.exists() and new_result.exists():
            old_data = _read_json(old_result)
            new_data = _read_json(new_result)
            equal = old_data == new_data

        return {
            "old_returncode": old_run.returncode,
            "new_returncode": new_run.returncode,
            "old_stdout_tail": old_run.stdout[-4000:],
            "new_stdout_tail": new_run.stdout[-4000:],
            "equal": equal,
            "old_result_sha256": _sha256(report_dir / "old_e2e_test_knowledge.json")
            if (report_dir / "old_e2e_test_knowledge.json").exists()
            else None,
            "new_result_sha256": _sha256(report_dir / "new_e2e_test_knowledge.json")
            if (report_dir / "new_e2e_test_knowledge.json").exists()
            else None,
        }
    finally:
        restore_file(old_api_config, old_api_original)
        restore_file(old_cache, old_cache_original)
        restore_file(old_result, old_result_original)
        if new_dataset.exists():
            shutil.rmtree(new_dataset)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-root", default=r"D:\PythonProjects\HyperGraphRAG")
    parser.add_argument("--new-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--dataset", default="hotpotqa_probe")
    parser.add_argument("--parity-dataset", default="hotpotqa_probe_parity")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--low-keywords", default=DEFAULT_LOW_KEYWORDS)
    parser.add_argument("--high-keywords", default=DEFAULT_HIGH_KEYWORDS)
    parser.add_argument(
        "--run-e2e-cache-replay",
        action="store_true",
        help=(
            "Run a live DeepSeek end-to-end probe after strict fixed-input checks. "
            "This is recorded for diagnostics only because only_need_context=True "
            "does not cache keyword extraction responses."
        ),
    )
    args = parser.parse_args()

    old_root = Path(args.old_root).resolve()
    new_root = Path(args.new_root).resolve()
    report_dir = new_root / "reports" / "parity" / args.dataset
    report_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "old_root": str(old_root),
        "new_root": str(new_root),
        "dataset": args.dataset,
        "parity_dataset": args.parity_dataset,
        "query": args.query,
        "low_keywords": args.low_keywords,
        "high_keywords": args.high_keywords,
        "core_files": compare_core_files(old_root, new_root),
    }
    report["core_files_equal"] = all(row["equal"] for row in report["core_files"])

    report["fixed_input_checks"] = run_child_checks(
        args.python,
        old_root,
        new_root,
        args.dataset,
        args.parity_dataset,
        report_dir,
        args.query,
        args.low_keywords,
        args.high_keywords,
    )

    if args.run_e2e_cache_replay:
        env_values = load_env_mapping(new_root / ".env")
        report["live_e2e_probe"] = run_e2e_cache_replay(
            args.python,
            old_root,
            new_root,
            args.dataset,
            args.parity_dataset,
            report_dir,
            env_values,
        )
        report["live_e2e_probe"]["strict_parity_gate"] = False
        report["live_e2e_probe"]["note"] = (
            "This probe uses live keyword extraction. It is not a strict parity gate "
            "because only_need_context=True returns before writing the final context "
            "to llm_response_cache, and keyword extraction itself is not cached."
        )

    report["pass"] = bool(
        report["core_files_equal"]
        and report["fixed_input_checks"].get("solver_equal")
        and report["fixed_input_checks"].get("context_equal")
    )

    _write_json(report_dir / "parity_report.json", report)
    print(json.dumps({"report": str(report_dir / "parity_report.json"), "pass": report["pass"]}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
