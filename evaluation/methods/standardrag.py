from __future__ import annotations

import argparse
import asyncio
import json
import os

from hypergraphrag import QueryParam
from hypergraphrag.utils import list_of_list_to_csv, truncate_list_by_token_size

from methods.common import build_rag, load_question_data, save_knowledge_results


def format_sources_context(chunk_items: list[dict]) -> str:
    csv_rows = [["id", "\tcontent"]]
    for idx, item in enumerate(chunk_items, start=1):
        csv_rows.append([str(idx), f"\t{item['content']}"])
    csv_text = list_of_list_to_csv(csv_rows)
    return f"\n-----Sources-----\n```csv\n{csv_text}```\n"


def resolve_context_budget() -> int:
    env_budget = os.getenv("HGRAG_STANDARDRAG_TOKEN_BUDGET")
    if env_budget:
        return int(env_budget)
    default_param = QueryParam()
    return (
        default_param.max_token_for_text_unit
        + default_param.max_token_for_global_context
        + default_param.max_token_for_local_context
    )


def resolve_chunk_top_k() -> int:
    env_top_k = os.getenv("HGRAG_STANDARDRAG_TOP_K")
    if env_top_k:
        return int(env_top_k)
    return QueryParam().top_k


async def run(data_source: str, chunk_top_k: int | None = None, token_budget: int | None = None):
    rag, query_concurrency = build_rag(data_source, env_name="HGRAG_STANDARDRAG_QUERY_CONCURRENCY")
    chunk_top_k = chunk_top_k if chunk_top_k is not None else resolve_chunk_top_k()
    token_budget = token_budget if token_budget is not None else resolve_context_budget()
    data, questions = load_question_data(data_source)
    print(
        json.dumps(
            {
                "event": "standardrag_dense_chunk_config",
                "data_source": data_source,
                "chunk_top_k": chunk_top_k,
                "token_budget": token_budget,
                "query_concurrency": query_concurrency,
            },
            ensure_ascii=False,
        )
    )
    sem = asyncio.Semaphore(query_concurrency)

    async def retrieve_dense_chunks(question: str) -> str:
        chunk_hits = await rag.chunks_vdb.query(question, top_k=chunk_top_k)
        if not chunk_hits:
            return format_sources_context([])
        chunk_ids = [item["id"] for item in chunk_hits]
        chunk_payloads = await rag.text_chunks.get_by_ids(chunk_ids)
        ordered_chunks = []
        for rank, (hit, payload) in enumerate(zip(chunk_hits, chunk_payloads), start=1):
            if payload is None:
                continue
            ordered_chunks.append(
                {
                    "id": hit["id"],
                    "rank": rank,
                    "distance": hit.get("distance", 0.0),
                    "content": payload["content"].strip(),
                    "tokens": payload.get("tokens", 0),
                    "full_doc_id": payload.get("full_doc_id"),
                    "chunk_order_index": payload.get("chunk_order_index"),
                }
            )
        truncated_chunks = truncate_list_by_token_size(
            ordered_chunks,
            key=lambda item: item["content"],
            max_token_size=token_budget,
        )
        return format_sources_context(truncated_chunks)

    async def query_with_semaphore(question: str) -> str:
        async with sem:
            return await retrieve_dense_chunks(question)

    results = await asyncio.gather(*[query_with_semaphore(question) for question in questions])
    for item, knowledge in zip(data, results):
        item["knowledge"] = knowledge
    return save_knowledge_results("StandardRAG", data_source, data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_source", default="hypertension")
    parser.add_argument("--chunk_top_k", type=int, default=None)
    parser.add_argument("--token_budget", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.data_source, chunk_top_k=args.chunk_top_k, token_budget=args.token_budget))


if __name__ == "__main__":
    main()
