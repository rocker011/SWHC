from __future__ import annotations

import argparse
import json

from methods.graphrag_official_common import build_official_graphrag_index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    parser.add_argument("--doc_limit", type=int, default=None)
    parser.add_argument("--workspace_suffix", default=None)
    parser.add_argument("--force_rebuild", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = build_official_graphrag_index(
        args.data_source,
        doc_limit=args.doc_limit,
        workspace_suffix=args.workspace_suffix,
        force_rebuild=args.force_rebuild,
        verbose=args.verbose,
    )
    pipeline_summaries = []
    failed_workflows = []
    for entry in result["pipeline_results"]:
        has_error = entry.error is not None
        pipeline_summaries.append(
            {
                "workflow": entry.workflow,
                "has_error": has_error,
            }
        )
        if has_error:
            failed_workflows.append(entry.workflow)

    print(
        json.dumps(
            {
                "event": "graphrag_official_step1_complete",
                "data_source": args.data_source,
                "workspace": result["workspace"].as_posix(),
                "documents": result["documents"],
                "input_snapshot_path": result["input_snapshot_path"].as_posix(),
                "chat_model": result["model_config"].chat_model,
                "chat_api_base": result["model_config"].chat_api_base,
                "embed_model": result["model_config"].embed_model,
                "embed_api_base": result["model_config"].embed_api_base,
                "failed_workflows": failed_workflows,
                "pipeline_results": pipeline_summaries,
            },
            ensure_ascii=False,
        )
    )
    if failed_workflows:
        raise SystemExit(
            "Official GraphRAG indexing failed in workflows: "
            + ", ".join(failed_workflows)
        )


if __name__ == "__main__":
    main()
