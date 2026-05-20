from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tqdm.auto import tqdm

from methods.common import load_question_data, save_knowledge_results
from methods.graphrag_official_common import (
    build_local_context_runner,
    format_local_context_records,
    resolve_graphrag_workspace,
)


BASE_DIR = Path(__file__).resolve().parents[1]


def remove_stale_downstream_outputs(data_source: str) -> list[Path]:
    result_dir = BASE_DIR / "results" / "GraphRAG" / data_source
    removed_paths: list[Path] = []
    for filename in ("test_generation.json", "test_result.json", "test_score.json"):
        target = result_dir / filename
        if target.exists():
            target.unlink()
            removed_paths.append(target)
    return removed_paths


def run(
    data_source: str,
    *,
    workspace_suffix: str | None = None,
    community_level: int | None = None,
) -> Path:
    workspace = resolve_graphrag_workspace(data_source, workspace_suffix)
    runner = build_local_context_runner(
        data_source,
        workspace_suffix=workspace_suffix,
        community_level=community_level,
    )
    data, questions = load_question_data(data_source)
    removed_paths = remove_stale_downstream_outputs(data_source)

    print(
        json.dumps(
            {
                "event": "graphrag_official_step2_config",
                "data_source": data_source,
                "workspace": workspace.as_posix(),
                "community_level": community_level
                if community_level is not None
                else int(os.getenv("HGRAG_GRAPHRAG_COMMUNITY_LEVEL", "2")),
                "query_count": len(questions),
                "cleared_stale_outputs": [path.as_posix() for path in removed_paths],
            },
            ensure_ascii=False,
        )
    )

    for item, question in tqdm(
        list(zip(data, questions)),
        total=len(questions),
        desc=f"GraphRAG[{data_source}] Step2",
    ):
        context_records = runner.build_context_records(question)
        item["knowledge"] = format_local_context_records(context_records)

    save_path = save_knowledge_results("GraphRAG", data_source, data)
    print(f"Results saved to {save_path.as_posix()}")
    return save_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    parser.add_argument("--workspace_suffix", default=None)
    parser.add_argument("--community_level", type=int, default=None)
    args = parser.parse_args()
    run(
        args.data_source,
        workspace_suffix=args.workspace_suffix,
        community_level=args.community_level,
    )


if __name__ == "__main__":
    main()
