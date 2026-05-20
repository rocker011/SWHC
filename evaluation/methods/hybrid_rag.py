from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict

from hypergraphrag import QueryParam
from hypergraphrag.utils import list_of_list_to_csv, truncate_list_by_token_size

from methods.common import BM25ChunkIndex, build_rag, load_question_data, save_knowledge_results


def format_sources_context(chunk_items: list[dict]) -> str:
    csv_rows = [["id", "\tcontent"]]
    for idx, item in enumerate(chunk_items, start=1):
        csv_rows.append([str(idx), f"\t{item['content']}"])
    csv_text = list_of_list_to_csv(csv_rows)
    return f"\n-----Sources-----\n```csv\n{csv_text}```\n"


def resolve_context_budget() -> int:
    env_budget = os.getenv("HGRAG_HYBRID_TOKEN_BUDGET")
    if env_budget:
        return int(env_budget)
    default_param = QueryParam()
    return (
        default_param.max_token_for_text_unit
        + default_param.max_token_for_global_context
        + default_param.max_token_for_local_context
    )


def resolve_bm25_top_k() -> int:
    env_top_k = os.getenv("HGRAG_HYBRID_BM25_TOP_K")
    if env_top_k:
        return int(env_top_k)
    return QueryParam().top_k


def resolve_dense_top_k() -> int:
    env_top_k = os.getenv("HGRAG_HYBRID_DENSE_TOP_K")
    if env_top_k:
        return int(env_top_k)
    return QueryParam().top_k


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    *,
    rrf_k: int,
) -> list[dict]:
    fused_scores: dict[str, float] = defaultdict(float)
    fused_records: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            chunk_id = item["id"]
            fused_scores[chunk_id] += 1.0 / (rrf_k + rank)
            if chunk_id not in fused_records:
                fused_records[chunk_id] = item
            else:
                fused_records[chunk_id] = {
                    **fused_records[chunk_id],
                    **item,
                }

    return [
        {
            **fused_records[chunk_id],
            "hybrid_score": score,
        }
        for chunk_id, score in sorted(
            fused_scores.items(),
            key=lambda item: (
                -item[1],
                fused_records[item[0]].get("full_doc_id") or "",
                fused_records[item[0]].get("chunk_order_index", 0),
                item[0],
            ),
        )
    ]


async def run(
    data_source: str,
    *,
    bm25_top_k: int | None = None,
    dense_top_k: int | None = None,
    token_budget: int | None = None,
    rrf_k: int | None = None,
):
    rag, query_concurrency = build_rag(data_source, env_name="HGRAG_HYBRID_QUERY_CONCURRENCY")
    index = BM25ChunkIndex.from_data_source(data_source)
    bm25_top_k = bm25_top_k if bm25_top_k is not None else resolve_bm25_top_k()
    dense_top_k = dense_top_k if dense_top_k is not None else resolve_dense_top_k()
    token_budget = token_budget if token_budget is not None else resolve_context_budget()
    rrf_k = rrf_k if rrf_k is not None else int(os.getenv("HGRAG_HYBRID_RRF_K", "60"))
    data, questions = load_question_data(data_source)
    print(
        json.dumps(
            {
                "event": "hybrid_chunk_config",
                "data_source": data_source,
                "bm25_top_k": bm25_top_k,
                "dense_top_k": dense_top_k,
                "token_budget": token_budget,
                "rrf_k": rrf_k,
                "query_concurrency": query_concurrency,
            },
            ensure_ascii=False,
        )
    )
    sem = asyncio.Semaphore(query_concurrency)

    async def retrieve_hybrid_chunks(question: str) -> str:
        bm25_hits = await asyncio.to_thread(index.query, question, top_k=bm25_top_k)
        dense_hits = await rag.chunks_vdb.query(question, top_k=dense_top_k)
        dense_chunk_ids = [item["id"] for item in dense_hits]
        dense_payloads = await rag.text_chunks.get_by_ids(dense_chunk_ids)
        dense_records = []
        for rank, (hit, payload) in enumerate(zip(dense_hits, dense_payloads), start=1):
            if payload is None:
                continue
            dense_records.append(
                {
                    "id": hit["id"],
                    "rank": rank,
                    "distance": hit.get("distance", 0.0),
                    "content": payload["content"].strip(),
                    "tokens": payload.get("tokens", 0),
                    "full_doc_id": payload.get("full_doc_id"),
                    "chunk_order_index": payload.get("chunk_order_index", 0),
                }
            )

        fused_hits = reciprocal_rank_fusion([bm25_hits, dense_records], rrf_k=rrf_k)
        truncated_chunks = truncate_list_by_token_size(
            fused_hits,
            key=lambda item: item["content"],
            max_token_size=token_budget,
        )
        return format_sources_context(truncated_chunks)

    async def query_with_semaphore(question: str) -> str:
        async with sem:
            return await retrieve_hybrid_chunks(question)

    results = await asyncio.gather(*[query_with_semaphore(question) for question in questions])
    for item, knowledge in zip(data, results):
        item["knowledge"] = knowledge
    return save_knowledge_results("HybridRAG", data_source, data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    parser.add_argument("--bm25_top_k", type=int, default=None)
    parser.add_argument("--dense_top_k", type=int, default=None)
    parser.add_argument("--token_budget", type=int, default=None)
    parser.add_argument("--rrf_k", type=int, default=None)
    args = parser.parse_args()
    save_path = asyncio.run(
        run(
            args.data_source,
            bm25_top_k=args.bm25_top_k,
            dense_top_k=args.dense_top_k,
            token_budget=args.token_budget,
            rrf_k=args.rrf_k,
        )
    )
    print(f"Results saved to {save_path.as_posix()}")


if __name__ == "__main__":
    main()
