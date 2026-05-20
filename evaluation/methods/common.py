from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
from typing import Callable

from tqdm.asyncio import tqdm_asyncio

from hypergraphrag import HyperGraphRAG, QueryParam
from hypergraphrag.openai_config import ensure_openai_api_key, is_local_embed_model


BASE_DIR = Path(__file__).resolve().parents[1]
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def resolve_query_concurrency(env_name: str = "HGRAG_QUERY_CONCURRENCY") -> tuple[dict, int]:
    rag_kwargs = {"working_dir": None}
    query_concurrency = int(os.getenv(env_name, "32"))
    if is_local_embed_model():
        rag_kwargs["embedding_func_max_async"] = 1
        query_concurrency = int(os.getenv(env_name, "2"))
    return rag_kwargs, query_concurrency


def build_rag(data_source: str, env_name: str = "HGRAG_QUERY_CONCURRENCY") -> tuple[HyperGraphRAG, int]:
    ensure_openai_api_key()
    rag_kwargs, query_concurrency = resolve_query_concurrency(env_name)
    rag_kwargs["working_dir"] = f"expr/{data_source}"
    return HyperGraphRAG(**rag_kwargs), query_concurrency


def load_question_data(data_source: str) -> tuple[list[dict], list[str]]:
    dataset_path = BASE_DIR / "datasets" / data_source / "questions.json"
    with dataset_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data, [item["question"] for item in data]


def load_text_chunks(data_source: str) -> list[dict]:
    chunk_store_path = BASE_DIR / "expr" / data_source / "kv_store_text_chunks.json"
    with chunk_store_path.open(encoding="utf-8") as handle:
        chunk_store = json.load(handle)

    chunks = []
    for chunk_id, payload in chunk_store.items():
        content = payload.get("content", "").strip()
        if not content:
            continue
        chunks.append(
            {
                "id": chunk_id,
                "tokens": payload.get("tokens", 0),
                "content": content,
                "full_doc_id": payload.get("full_doc_id"),
                "chunk_order_index": payload.get("chunk_order_index", 0),
            }
        )
    chunks.sort(
        key=lambda item: (
            item.get("full_doc_id") or "",
            item.get("chunk_order_index", 0),
            item["id"],
        )
    )
    return chunks


def tokenize_for_bm25(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


@dataclass
class BM25ChunkIndex:
    chunk_records: list[dict]
    postings: dict[str, list[tuple[int, int]]]
    doc_lengths: list[int]
    idf_by_term: dict[str, float]
    avg_doc_length: float
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def from_chunks(
        cls,
        chunk_records: list[dict],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "BM25ChunkIndex":
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        doc_lengths: list[int] = []
        document_count = len(chunk_records)

        for doc_idx, record in enumerate(chunk_records):
            terms = tokenize_for_bm25(record["content"])
            doc_lengths.append(len(terms))
            for term, term_freq in Counter(terms).items():
                postings[term].append((doc_idx, term_freq))

        avg_doc_length = sum(doc_lengths) / document_count if document_count else 0.0
        idf_by_term = {
            term: math.log(1.0 + (document_count - len(doc_freqs) + 0.5) / (len(doc_freqs) + 0.5))
            for term, doc_freqs in postings.items()
        }
        return cls(
            chunk_records=chunk_records,
            postings=dict(postings),
            doc_lengths=doc_lengths,
            idf_by_term=idf_by_term,
            avg_doc_length=avg_doc_length,
            k1=k1,
            b=b,
        )

    @classmethod
    def from_data_source(
        cls,
        data_source: str,
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "BM25ChunkIndex":
        return cls.from_chunks(load_text_chunks(data_source), k1=k1, b=b)

    def query(self, query: str, *, top_k: int) -> list[dict]:
        if top_k <= 0 or not self.chunk_records:
            return []

        query_terms = Counter(tokenize_for_bm25(query))
        if not query_terms:
            return []

        scores: dict[int, float] = defaultdict(float)
        avg_doc_length = self.avg_doc_length if self.avg_doc_length > 0 else 1.0

        for term, query_tf in query_terms.items():
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = self.idf_by_term[term]
            for doc_idx, term_freq in postings:
                doc_length = self.doc_lengths[doc_idx]
                denom = term_freq + self.k1 * (
                    1 - self.b + self.b * (doc_length / avg_doc_length)
                )
                scores[doc_idx] += query_tf * idf * ((term_freq * (self.k1 + 1)) / denom)

        ranked_doc_ids = sorted(
            scores,
            key=lambda doc_idx: (
                -scores[doc_idx],
                self.chunk_records[doc_idx].get("full_doc_id") or "",
                self.chunk_records[doc_idx].get("chunk_order_index", 0),
                self.chunk_records[doc_idx]["id"],
            ),
        )[:top_k]

        results = []
        for rank, doc_idx in enumerate(ranked_doc_ids, start=1):
            record = self.chunk_records[doc_idx]
            results.append(
                {
                    **record,
                    "rank": rank,
                    "bm25_score": scores[doc_idx],
                }
            )
        return results


def save_knowledge_results(method_name: str, data_source: str, data: list[dict]) -> Path:
    save_path = BASE_DIR / "results" / method_name / data_source / "test_knowledge.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if save_path.exists():
        save_path.unlink()
    save_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    return save_path


async def run_query_method(
    *,
    data_source: str,
    method_name: str,
    query_param_factory: Callable[[], QueryParam],
    env_name: str = "HGRAG_QUERY_CONCURRENCY",
) -> Path:
    rag, query_concurrency = build_rag(data_source, env_name=env_name)
    data, questions = load_question_data(data_source)
    sem = asyncio.Semaphore(query_concurrency)

    async def query_with_semaphore(question: str) -> str:
        async with sem:
            return await rag.aquery(question, query_param_factory())

    tasks = [query_with_semaphore(question) for question in questions]
    results = await tqdm_asyncio.gather(*tasks)

    for item, knowledge in zip(data, results):
        item["knowledge"] = knowledge

    save_path = save_knowledge_results(method_name, data_source, data)
    print(f"Results saved to {save_path.as_posix()}")
    return save_path
