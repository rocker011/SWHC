from __future__ import annotations

import asyncio
from collections import defaultdict
from itertools import combinations
from typing import Any

from .base import BaseGraphStorage, BaseKVStorage, QueryParam, TextChunkSchema
from .prompt import GRAPH_FIELD_SEP
from .utils import (
    list_of_list_to_csv,
    logger,
    split_string_by_multi_markers,
    truncate_list_by_token_size,
)


def _normalize_scores(score_map: dict[str, float]) -> dict[str, float]:
    if not score_map:
        return {}
    values = list(score_map.values())
    min_v = min(values)
    max_v = max(values)
    if abs(max_v - min_v) < 1e-8:
        return {key: 1.0 for key in score_map}
    return {key: (value - min_v) / (max_v - min_v) for key, value in score_map.items()}


def _iter_source_ids(raw_value: Any) -> list[str]:
    if not raw_value:
        return []
    return [
        item
        for item in split_string_by_multi_markers(str(raw_value), [GRAPH_FIELD_SEP])
        if item
    ]


async def _recover_entity_seeds_from_hyperedges(
    knowledge_graph_inst: BaseGraphStorage,
    hyperedge_seeds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recovered: dict[str, dict[str, Any]] = {}
    for hyperedge_seed in hyperedge_seeds:
        node_id = hyperedge_seed["node_id"]
        neighbors = await knowledge_graph_inst.get_node_edges(node_id)
        for _, entity_id in neighbors or []:
            entity_data = await knowledge_graph_inst.get_node(entity_id)
            if entity_data is None:
                continue
            degree = await knowledge_graph_inst.node_degree(entity_id)
            score = float(hyperedge_seed.get("seed_score", 0.0)) * 0.8
            current = recovered.get(entity_id)
            if current is None or score > current["seed_score"]:
                recovered[entity_id] = {
                    **entity_data,
                    "node_id": entity_id,
                    "entity_name": entity_id,
                    "rank": degree,
                    "distance": hyperedge_seed.get("distance", 0.0),
                    "seed_score": score,
                }
    return sorted(recovered.values(), key=lambda item: item["seed_score"], reverse=True)


async def build_graphrag_context(
    knowledge_graph_inst: BaseGraphStorage,
    text_chunks_db: BaseKVStorage[TextChunkSchema],
    entity_seeds: list[dict[str, Any]],
    hyperedge_seeds: list[dict[str, Any]],
    query_param: QueryParam,
) -> tuple[str, str, str, dict[str, Any]]:
    entity_seeds = entity_seeds[: query_param.graphrag_seed_topk_entity]
    hyperedge_seeds = hyperedge_seeds[: query_param.graphrag_seed_topk_hyperedge]

    if not entity_seeds and hyperedge_seeds:
        entity_seeds = await _recover_entity_seeds_from_hyperedges(
            knowledge_graph_inst,
            hyperedge_seeds,
        )
        entity_seeds = entity_seeds[: query_param.graphrag_seed_topk_entity]

    if not entity_seeds:
        return "", "", "", {
            "seed_entities": 0,
            "selected_entities": 0,
            "selected_hyperedges": 0,
            "selected_sources": 0,
            "binary_relations": 0,
        }

    seed_scores = _normalize_scores(
        {seed["node_id"]: float(seed.get("seed_score", 0.0)) for seed in entity_seeds}
    )
    seed_ids = {seed["node_id"] for seed in entity_seeds}

    entity_neighbors = await asyncio.gather(
        *[knowledge_graph_inst.get_node_edges(seed_id) for seed_id in seed_ids]
    )
    hyperedge_ids = set()
    hyperedge_seed_scores: dict[str, float] = {}
    for seed_id, neighbors in zip(seed_ids, entity_neighbors):
        for _, hyperedge_id in neighbors or []:
            hyperedge_ids.add(hyperedge_id)
            hyperedge_seed_scores[hyperedge_id] = max(
                hyperedge_seed_scores.get(hyperedge_id, 0.0),
                seed_scores.get(seed_id, 0.0),
            )
    for hyperedge_seed in hyperedge_seeds:
        node_id = hyperedge_seed["node_id"]
        hyperedge_ids.add(node_id)
        hyperedge_seed_scores[node_id] = max(
            hyperedge_seed_scores.get(node_id, 0.0),
            float(hyperedge_seed.get("seed_score", 0.0)),
        )

    hyperedge_nodes = await asyncio.gather(
        *[knowledge_graph_inst.get_node(node_id) for node_id in hyperedge_ids]
    )
    hyperedge_rows = []
    for node_id, node_data in zip(hyperedge_ids, hyperedge_nodes):
        if node_data is None:
            continue
        score = hyperedge_seed_scores.get(node_id, 0.0)
        score += float(node_data.get("weight", 0.0)) / (float(node_data.get("weight", 0.0)) + 10.0) * 0.25
        hyperedge_rows.append({**node_data, "node_id": node_id, "score": score})
    hyperedge_rows.sort(key=lambda item: (item["score"], item.get("weight", 0.0)), reverse=True)
    hyperedge_rows = truncate_list_by_token_size(
        hyperedge_rows,
        key=lambda item: item["node_id"],
        max_token_size=query_param.max_token_for_global_context,
    )

    hyperedge_neighbors = await asyncio.gather(
        *[knowledge_graph_inst.get_node_edges(item["node_id"]) for item in hyperedge_rows]
    )
    neighbor_score_map: dict[str, float] = defaultdict(float)
    entity_to_hyperedges: dict[str, list[str]] = defaultdict(list)
    relation_candidates: list[dict[str, Any]] = []

    for hyperedge_item, neighbors in zip(hyperedge_rows, hyperedge_neighbors):
        entity_ids = []
        for _, entity_id in neighbors or []:
            entity_ids.append(entity_id)
            neighbor_score_map[entity_id] = max(
                neighbor_score_map.get(entity_id, 0.0),
                hyperedge_item["score"],
            )
            entity_to_hyperedges[entity_id].append(hyperedge_item["node_id"])
        relation_candidates.append(
            {
                "hyperedge": hyperedge_item["node_id"],
                "source_id": hyperedge_item.get("source_id", ""),
                "score": hyperedge_item["score"],
                "entity_ids": entity_ids,
            }
        )

    all_entity_ids = sorted(set(list(seed_ids) + list(neighbor_score_map.keys())))
    entity_nodes = await asyncio.gather(
        *[knowledge_graph_inst.get_node(entity_id) for entity_id in all_entity_ids]
    )
    entity_degrees = await asyncio.gather(
        *[knowledge_graph_inst.node_degree(entity_id) for entity_id in all_entity_ids]
    )

    selected_entities = []
    for entity_id, node_data, degree in zip(all_entity_ids, entity_nodes, entity_degrees):
        if node_data is None:
            continue
        score = max(seed_scores.get(entity_id, 0.0), neighbor_score_map.get(entity_id, 0.0) * 0.8)
        score += min(float(degree), 20.0) / 20.0 * 0.2
        selected_entities.append(
            {
                **node_data,
                "node_id": entity_id,
                "entity_name": entity_id,
                "rank": degree,
                "score": score,
            }
        )
    selected_entities.sort(key=lambda item: item["score"], reverse=True)
    selected_entities = truncate_list_by_token_size(
        selected_entities,
        key=lambda item: item.get("description", ""),
        max_token_size=query_param.max_token_for_local_context,
    )
    selected_entity_ids = {item["node_id"] for item in selected_entities}
    selected_entity_score_map = {
        item["node_id"]: item["score"] for item in selected_entities
    }

    binary_relations = []
    seen_relations = set()
    for relation in relation_candidates:
        entity_ids = [entity_id for entity_id in relation["entity_ids"] if entity_id in selected_entity_ids]
        if len(entity_ids) < 2:
            continue
        entity_ids.sort(key=lambda entity_id: selected_entity_score_map.get(entity_id, 0.0), reverse=True)
        seed_entities = [entity_id for entity_id in entity_ids if entity_id in seed_ids]
        candidate_pairs = []
        if seed_entities:
            for seed_entity in seed_entities:
                for other_entity in entity_ids:
                    if other_entity == seed_entity:
                        continue
                    candidate_pairs.append((seed_entity, other_entity))
        else:
            candidate_pairs.extend(combinations(entity_ids, 2))
        scored_pairs = []
        for left, right in candidate_pairs:
            pair_key = tuple(sorted((left, right)) + [relation["hyperedge"]])
            if pair_key in seen_relations:
                continue
            pair_score = (
                selected_entity_score_map.get(left, 0.0)
                + selected_entity_score_map.get(right, 0.0)
                + relation["score"]
            )
            scored_pairs.append((pair_score, left, right, pair_key))
        scored_pairs.sort(reverse=True)
        for pair_score, left, right, pair_key in scored_pairs[: query_param.graphrag_max_pairs_per_hyperedge]:
            seen_relations.add(pair_key)
            binary_relations.append(
                {
                    "src": left,
                    "tgt": right,
                    "relation": relation["hyperedge"],
                    "score": pair_score,
                    "source_id": relation["source_id"],
                }
            )
    binary_relations.sort(key=lambda item: item["score"], reverse=True)
    binary_relations = truncate_list_by_token_size(
        binary_relations,
        key=lambda item: item["relation"],
        max_token_size=query_param.max_token_for_global_context,
    )

    source_support = defaultdict(int)
    for entity in selected_entities:
        for source_id in _iter_source_ids(entity.get("source_id")):
            source_support[source_id] += 1
    for relation in binary_relations:
        for source_id in _iter_source_ids(relation.get("source_id")):
            source_support[source_id] += 1
    for hyperedge in hyperedge_rows:
        for source_id in _iter_source_ids(hyperedge.get("source_id")):
            source_support[source_id] += 1

    source_rows = []
    if source_support:
        source_ids = list(source_support.keys())
        chunks = await text_chunks_db.get_by_ids(source_ids)
        for source_id, chunk in zip(source_ids, chunks):
            if chunk is None or "content" not in chunk:
                continue
            source_rows.append(
                {
                    "id": source_id,
                    "content": chunk["content"],
                    "support": source_support[source_id],
                }
            )
        source_rows.sort(key=lambda item: (-item["support"], item["id"]))
        source_rows = truncate_list_by_token_size(
            source_rows,
            key=lambda item: item["content"],
            max_token_size=query_param.max_token_for_text_unit,
        )

    entities_section_list = [["id", "entity", "type", "description"]]
    for index, entity in enumerate(selected_entities):
        entities_section_list.append(
            [
                index,
                entity["entity_name"],
                entity.get("entity_type", "UNKNOWN"),
                entity.get("description", "UNKNOWN"),
            ]
        )

    relations_section_list = [["id", "source_entity", "target_entity", "relation"]]
    for index, relation in enumerate(binary_relations):
        relations_section_list.append(
            [
                index,
                relation["src"],
                relation["tgt"],
                relation["relation"],
            ]
        )

    sources_section_list = [["id", "content"]]
    for index, row in enumerate(source_rows):
        sources_section_list.append([index, row["content"]])

    logger.info(
        "GraphRAG baseline uses %s seed entities, %s entities, %s binary relations, %s text units",
        len(entity_seeds),
        len(selected_entities),
        len(binary_relations),
        len(source_rows),
    )

    debug = {
        "seed_entities": len(entity_seeds),
        "selected_entities": len(selected_entities),
        "selected_hyperedges": len(hyperedge_rows),
        "selected_sources": len(source_rows),
        "binary_relations": len(binary_relations),
        "seed_entity_ids": [seed["node_id"] for seed in entity_seeds],
    }

    return (
        list_of_list_to_csv(entities_section_list),
        list_of_list_to_csv(relations_section_list),
        list_of_list_to_csv(sources_section_list),
        debug,
    )
