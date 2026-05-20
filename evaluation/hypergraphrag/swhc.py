from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
import re
from typing import Any

import networkx as nx

from .base import BaseGraphStorage, BaseKVStorage, QueryParam, TextChunkSchema
from .prompt import GRAPH_FIELD_SEP
from .utils import (
    encode_string_by_tiktoken,
    list_of_list_to_csv,
    logger,
    split_string_by_multi_markers,
    truncate_list_by_token_size,
)


@dataclass
class SWHCResult:
    subgraph: nx.Graph
    debug: dict[str, Any]


_SOURCE_RERANK_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_SOURCE_RERANK_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "whose",
    "with",
}


def _normalize_score_map(score_map: dict[str, float]) -> dict[str, float]:
    if not score_map:
        return {}
    values = list(score_map.values())
    min_v = min(values)
    max_v = max(values)
    if abs(max_v - min_v) < 1e-8:
        return {k: 1.0 for k in score_map}
    return {k: (v - min_v) / (max_v - min_v) for k, v in score_map.items()}


def _token_len(text: str, tiktoken_model: str) -> int:
    if not text:
        return 0
    return len(encode_string_by_tiktoken(text, model_name=tiktoken_model))


def _node_text(node_id: str, node_data: dict[str, Any]) -> str:
    role = node_data.get("role", "")
    if role == "entity":
        return f"{node_id} {node_data.get('description', '')}"
    return node_id


def _iter_source_ids(source_id_value: Any) -> list[str]:
    if not source_id_value:
        return []
    return [
        source_id
        for source_id in split_string_by_multi_markers(str(source_id_value), [GRAPH_FIELD_SEP])
        if source_id
    ]


def _source_rerank_tokens(text: str) -> set[str]:
    tokens = _SOURCE_RERANK_TOKEN_PATTERN.findall((text or "").lower())
    return {
        token
        for token in tokens
        if len(token) > 1 and token not in _SOURCE_RERANK_STOPWORDS
    }


def _query_source_overlap(query_tokens: set[str], source_tokens: set[str]) -> float:
    if not query_tokens or not source_tokens:
        return 0.0
    return len(query_tokens & source_tokens) / len(query_tokens)


def _terminal_search_text(node_id: str) -> str:
    text = str(node_id or "").replace("<hyperedge>", " ")
    text = re.sub(r"[_\"'<>]+", " ", text)
    return " ".join(text.lower().split())


def _terminal_mentioned_in_source(terminal_text: str, source_text: str) -> bool:
    if not terminal_text:
        return False
    normalized_source = " ".join((source_text or "").lower().split())
    if terminal_text in normalized_source:
        return True
    terminal_tokens = _source_rerank_tokens(terminal_text)
    source_tokens = _source_rerank_tokens(normalized_source)
    if not terminal_tokens:
        return False
    return len(terminal_tokens & source_tokens) / len(terminal_tokens) >= 0.8


def _copy_path_into_graph(target: nx.Graph, source: nx.Graph, path: list[str]) -> None:
    for node_id in path:
        if source.has_node(node_id):
            target.add_node(node_id, **source.nodes[node_id])
    for left, right in zip(path, path[1:]):
        if source.has_edge(left, right):
            target.add_edge(left, right, **source.edges[left, right])


def _compute_terminal_weights(
    terminals: list[str], seed_scores: dict[str, float]
) -> dict[str, float]:
    raw = {t: max(seed_scores.get(t, 0.1), 0.05) for t in terminals}
    total = sum(raw.values())
    if total <= 0:
        uniform = 1.0 / max(len(terminals), 1)
        return {t: uniform for t in terminals}
    return {t: raw[t] / total for t in terminals}


def _compute_objective(
    graph: nx.Graph,
    terminals: list[str],
    terminal_weights: dict[str, float],
    node_scores: dict[str, float],
    query_param: QueryParam,
    tiktoken_model_name: str,
) -> tuple[float, dict[str, float]]:
    if not terminals:
        return 0.0, {"wiener": 0.0, "node_cost": 0.0, "size_penalty": 0.0}
    present_terminals = [t for t in terminals if graph.has_node(t)]
    if len(present_terminals) != len(terminals):
        return float("inf"), {
            "wiener": float("inf"),
            "node_cost": float("inf"),
            "size_penalty": float("inf"),
        }
    try:
        all_lengths = dict(nx.all_pairs_dijkstra_path_length(graph, weight="swhc_weight"))
    except nx.NetworkXNoPath:
        return float("inf"), {
            "wiener": float("inf"),
            "node_cost": float("inf"),
            "size_penalty": float("inf"),
        }

    wiener = 0.0
    for left, right in combinations(terminals, 2):
        dist = all_lengths.get(left, {}).get(right)
        if dist is None:
            return float("inf"), {
                "wiener": float("inf"),
                "node_cost": float("inf"),
                "size_penalty": float("inf"),
            }
        wiener += terminal_weights[left] * terminal_weights[right] * dist

    node_cost = 0.0
    for node_id, node_data in graph.nodes(data=True):
        node_text = _node_text(node_id, node_data)
        token_cost = _token_len(node_text, tiktoken_model_name) / 256.0
        semantic_penalty = 1.0 - node_scores.get(node_id, 0.0)
        node_cost += token_cost + semantic_penalty

    size_penalty = float(graph.number_of_nodes())
    total = (
        query_param.swhc_alpha * wiener
        + query_param.swhc_beta * node_cost
        + query_param.swhc_gamma * size_penalty
    )
    return total, {
        "wiener": round(wiener, 6),
        "node_cost": round(node_cost, 6),
        "size_penalty": round(size_penalty, 6),
    }


def _add_semantic_edge_weights(
    candidate_graph: nx.Graph,
    node_scores: dict[str, float],
    query_param: QueryParam,
) -> None:
    for left, right, edge_data in candidate_graph.edges(data=True):
        confidence = float(edge_data.get("weight", 1.0))
        semantic_bonus = (node_scores.get(left, 0.0) + node_scores.get(right, 0.0)) / 2.0
        base_weight = 1.0 / max(confidence, 1.0) ** 0.5
        semantic_penalty = 1.0 - semantic_bonus
        edge_data["swhc_weight"] = max(
            query_param.swhc_edge_weight_floor,
            base_weight + semantic_penalty + query_param.swhc_hop_cost,
        )


def _initialize_connector_subgraph(
    candidate_graph: nx.Graph,
    terminals: list[str],
) -> nx.Graph:
    subgraph = nx.Graph()
    if not terminals:
        return subgraph

    complete_graph = nx.Graph()
    path_lookup: dict[tuple[str, str], list[str]] = {}
    for terminal in terminals:
        if candidate_graph.has_node(terminal):
            complete_graph.add_node(terminal)

    for left, right in combinations(terminals, 2):
        if not candidate_graph.has_node(left) or not candidate_graph.has_node(right):
            continue
        try:
            path = nx.shortest_path(
                candidate_graph, left, right, weight="swhc_weight"
            )
            path_cost = nx.path_weight(candidate_graph, path, weight="swhc_weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        complete_graph.add_edge(left, right, weight=path_cost)
        path_lookup[(left, right)] = path
        path_lookup[(right, left)] = list(reversed(path))

    for component in nx.connected_components(complete_graph):
        component = list(component)
        if len(component) == 1:
            node_id = component[0]
            subgraph.add_node(node_id, **candidate_graph.nodes[node_id])
            continue
        mst = nx.minimum_spanning_tree(complete_graph.subgraph(component), weight="weight")
        for left, right in mst.edges():
            path = path_lookup.get((left, right))
            if path:
                _copy_path_into_graph(subgraph, candidate_graph, path)

    for terminal in terminals:
        if candidate_graph.has_node(terminal) and not subgraph.has_node(terminal):
            subgraph.add_node(terminal, **candidate_graph.nodes[terminal])

    return subgraph


def _augment_connector_subgraph(
    candidate_graph: nx.Graph,
    subgraph: nx.Graph,
    terminals: list[str],
    terminal_weights: dict[str, float],
    node_scores: dict[str, float],
    query_param: QueryParam,
    tiktoken_model_name: str,
) -> tuple[nx.Graph, list[list[str]]]:
    added_paths: list[list[str]] = []
    current_graph = subgraph.copy()
    current_score, _ = _compute_objective(
        current_graph,
        terminals,
        terminal_weights,
        node_scores,
        query_param,
        tiktoken_model_name,
    )
    if current_graph.number_of_nodes() >= query_param.swhc_budget_nodes:
        return current_graph, added_paths

    for _ in range(query_param.swhc_bridge_max_iters):
        try:
            current_lengths = dict(
                nx.all_pairs_dijkstra_path_length(current_graph, weight="swhc_weight")
            )
        except nx.NetworkXNoPath:
            current_lengths = {}

        far_pairs = []
        for left, right in combinations(terminals, 2):
            dist = current_lengths.get(left, {}).get(right, float("inf"))
            far_pairs.append((dist, left, right))
        far_pairs.sort(reverse=True)

        best_gain = 0.0
        best_graph = None
        best_path = None
        for _, left, right in far_pairs[: min(10, len(far_pairs))]:
            try:
                path = nx.shortest_path(candidate_graph, left, right, weight="swhc_weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            new_nodes = [node for node in path if not current_graph.has_node(node)]
            if not new_nodes:
                continue
            if current_graph.number_of_nodes() + len(new_nodes) > query_param.swhc_budget_nodes:
                continue
            trial_graph = current_graph.copy()
            _copy_path_into_graph(trial_graph, candidate_graph, path)
            trial_score, _ = _compute_objective(
                trial_graph,
                terminals,
                terminal_weights,
                node_scores,
                query_param,
                tiktoken_model_name,
            )
            gain = current_score - trial_score
            if gain > best_gain:
                best_gain = gain
                best_graph = trial_graph
                best_path = path

        if best_graph is None or best_gain < query_param.swhc_min_gain:
            break
        current_graph = best_graph
        current_score -= best_gain
        if best_path is not None:
            added_paths.append(best_path)

    return current_graph, added_paths


def _prune_connector_subgraph(
    subgraph: nx.Graph,
    terminals: list[str],
    terminal_weights: dict[str, float],
    node_scores: dict[str, float],
    query_param: QueryParam,
    tiktoken_model_name: str,
) -> nx.Graph:
    if not query_param.swhc_enable_prune:
        return subgraph
    current_graph = subgraph.copy()
    improved = True
    while improved:
        improved = False
        base_score, _ = _compute_objective(
            current_graph,
            terminals,
            terminal_weights,
            node_scores,
            query_param,
            tiktoken_model_name,
        )
        for node_id in list(current_graph.nodes()):
            if node_id in terminals:
                continue
            if current_graph.degree(node_id) > 1:
                continue
            trial_graph = current_graph.copy()
            trial_graph.remove_node(node_id)
            trial_score, _ = _compute_objective(
                trial_graph,
                terminals,
                terminal_weights,
                node_scores,
                query_param,
                tiktoken_model_name,
            )
            if trial_score < base_score:
                current_graph = trial_graph
                improved = True
                break
    return current_graph


async def build_candidate_subgraph(
    knowledge_graph_inst: BaseGraphStorage,
    seed_nodes: list[str],
    hops: int,
) -> nx.Graph:
    candidate_graph = nx.Graph()
    if not seed_nodes:
        return candidate_graph

    queue = deque((seed_node, 0) for seed_node in seed_nodes)
    visited = set(seed_nodes)
    while queue:
        node_id, depth = queue.popleft()
        node_data = await knowledge_graph_inst.get_node(node_id)
        if node_data is None:
            continue
        candidate_graph.add_node(node_id, **node_data)
        if depth >= hops:
            continue
        edges = await knowledge_graph_inst.get_node_edges(node_id)
        if not edges:
            continue
        for left, right in edges:
            neighbor = right if left == node_id else left
            neighbor_data = await knowledge_graph_inst.get_node(neighbor)
            edge_data = await knowledge_graph_inst.get_edge(left, right)
            candidate_graph.add_node(neighbor, **(neighbor_data or {}))
            candidate_graph.add_edge(left, right, **(edge_data or {}))
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return candidate_graph


def _derive_node_scores(
    candidate_graph: nx.Graph,
    seed_scores: dict[str, float],
) -> dict[str, float]:
    normalized_seed_scores = _normalize_score_map(seed_scores)
    degrees = dict(candidate_graph.degree())
    normalized_degree = _normalize_score_map(
        {node_id: float(degree) for node_id, degree in degrees.items()}
    )
    node_scores = {}
    for node_id, node_data in candidate_graph.nodes(data=True):
        role = node_data.get("role", "")
        seed_score = normalized_seed_scores.get(node_id, 0.0)
        degree_score = normalized_degree.get(node_id, 0.0)
        if role == "hyperedge":
            raw_weight = float(node_data.get("weight", 1.0))
            weight_score = raw_weight / (raw_weight + 10.0)
            score = 0.55 * seed_score + 0.25 * weight_score + 0.20 * degree_score
        else:
            score = 0.70 * seed_score + 0.30 * degree_score
        node_scores[node_id] = max(0.0, min(1.0, score))
    return node_scores


async def solve_swhc(
    knowledge_graph_inst: BaseGraphStorage,
    text_chunks_db: BaseKVStorage[TextChunkSchema],
    entity_seeds: list[dict[str, Any]],
    hyperedge_seeds: list[dict[str, Any]],
    query_param: QueryParam,
    tiktoken_model_name: str,
) -> SWHCResult:
    entity_seeds = entity_seeds[: query_param.swhc_seed_topk_entity]
    hyperedge_seeds = hyperedge_seeds[: query_param.swhc_seed_topk_hyperedge]
    seed_scores = {
        seed["node_id"]: float(seed.get("seed_score", 0.0))
        for seed in entity_seeds + hyperedge_seeds
    }
    sorted_terminals = sorted(
        seed_scores.items(), key=lambda item: item[1], reverse=True
    )[: query_param.swhc_hard_terminal_topk]
    terminals = [node_id for node_id, _ in sorted_terminals]
    seed_nodes = [seed["node_id"] for seed in entity_seeds + hyperedge_seeds]

    candidate_graph = await build_candidate_subgraph(
        knowledge_graph_inst,
        seed_nodes=seed_nodes,
        hops=query_param.swhc_candidate_hops,
    )
    if candidate_graph.number_of_nodes() == 0:
        return SWHCResult(
            subgraph=nx.Graph(),
            debug={
                "terminals": terminals,
                "candidate_nodes": 0,
                "candidate_edges": 0,
                "selected_nodes": [],
                "added_bridge_paths": [],
                "objective": {},
            },
        )

    node_scores = _derive_node_scores(candidate_graph, seed_scores)
    _add_semantic_edge_weights(candidate_graph, node_scores, query_param)

    if not terminals:
        terminals = seed_nodes[: min(len(seed_nodes), query_param.swhc_hard_terminal_topk)]
    terminals = [node_id for node_id in terminals if candidate_graph.has_node(node_id)]
    terminal_weights = _compute_terminal_weights(terminals, seed_scores)

    subgraph = _initialize_connector_subgraph(candidate_graph, terminals)
    subgraph, added_bridge_paths = _augment_connector_subgraph(
        candidate_graph,
        subgraph,
        terminals,
        terminal_weights,
        node_scores,
        query_param,
        tiktoken_model_name,
    )
    subgraph = _prune_connector_subgraph(
        subgraph,
        terminals,
        terminal_weights,
        node_scores,
        query_param,
        tiktoken_model_name,
    )
    objective, objective_terms = _compute_objective(
        subgraph,
        terminals,
        terminal_weights,
        node_scores,
        query_param,
        tiktoken_model_name,
    )
    debug = {
        "terminals": terminals,
        "candidate_nodes": candidate_graph.number_of_nodes(),
        "candidate_edges": candidate_graph.number_of_edges(),
        "selected_nodes": list(subgraph.nodes()),
        "added_bridge_paths": added_bridge_paths,
        "objective": {**objective_terms, "total": round(objective, 6)}
        if objective != float("inf")
        else {"total": float("inf")},
    }
    subgraph.graph["node_scores"] = node_scores
    return SWHCResult(subgraph=subgraph, debug=debug)


async def format_swhc_context(
    swhc_result: SWHCResult,
    text_chunks_db: BaseKVStorage[TextChunkSchema],
    query_param: QueryParam,
    query_text: str = "",
) -> tuple[str, str, str]:
    subgraph = swhc_result.subgraph
    if subgraph.number_of_nodes() == 0:
        return "", "", ""

    node_scores = subgraph.graph.get("node_scores", {})

    entity_nodes = [
        (node_id, data)
        for node_id, data in subgraph.nodes(data=True)
        if data.get("role") == "entity"
    ]
    entity_nodes.sort(
        key=lambda item: (node_scores.get(item[0], 0.0), subgraph.degree(item[0])),
        reverse=True,
    )
    entity_nodes = truncate_list_by_token_size(
        entity_nodes,
        key=lambda item: f"{item[0]} {item[1].get('description', '')}",
        max_token_size=query_param.max_token_for_local_context,
    )

    hyperedge_nodes = [
        (node_id, data)
        for node_id, data in subgraph.nodes(data=True)
        if data.get("role") == "hyperedge"
    ]
    hyperedge_nodes.sort(
        key=lambda item: (node_scores.get(item[0], 0.0), item[1].get("weight", 0.0)),
        reverse=True,
    )
    hyperedge_nodes = truncate_list_by_token_size(
        hyperedge_nodes,
        key=lambda item: item[0],
        max_token_size=query_param.max_token_for_global_context,
    )

    entities_section_list = [["id", "entity", "type", "description"]]
    for index, (node_id, node_data) in enumerate(entity_nodes):
        entities_section_list.append(
            [
                index,
                node_id,
                node_data.get("entity_type", "UNKNOWN"),
                node_data.get("description", "UNKNOWN"),
            ]
        )
    entities_context = list_of_list_to_csv(entities_section_list)

    relations_section_list = [["id", "hyperedge", "related_entities"]]
    for index, (node_id, _) in enumerate(hyperedge_nodes):
        related_entities = sorted(
            [
                neighbor
                for neighbor in subgraph.neighbors(node_id)
                if subgraph.nodes[neighbor].get("role") == "entity"
            ]
        )
        relations_section_list.append(
            [index, node_id, "|".join(related_entities)]
        )
    relations_context = list_of_list_to_csv(relations_section_list)

    terminals = set(swhc_result.debug.get("terminals", []))
    terminal_texts = {
        terminal: _terminal_search_text(terminal)
        for terminal in terminals
        if subgraph.has_node(terminal)
    }
    query_tokens = _source_rerank_tokens(query_text)

    source_counter: Counter[str] = Counter()
    source_node_score: Counter[str] = Counter()
    source_terminal_hits: dict[str, set[str]] = defaultdict(set)
    for node_id, node_data in subgraph.nodes(data=True):
        for source_id in _iter_source_ids(node_data.get("source_id")):
            source_counter[source_id] += 1
            source_node_score[source_id] += float(node_scores.get(node_id, 0.0))
            if node_id in terminals:
                source_terminal_hits[source_id].add(node_id)
    for _, _, edge_data in subgraph.edges(data=True):
        for source_id in _iter_source_ids(edge_data.get("source_id")):
            source_counter[source_id] += 1

    text_units = []
    max_support = max(source_counter.values(), default=1)
    max_node_score = max(source_node_score.values(), default=1.0)
    for source_id, support in source_counter.items():
        chunk_data = await text_chunks_db.get_by_id(source_id)
        if chunk_data is None or "content" not in chunk_data:
            continue
        content = chunk_data["content"]
        source_tokens = _source_rerank_tokens(content)
        terminal_hits = set(source_terminal_hits.get(source_id, set()))
        for terminal, terminal_text in terminal_texts.items():
            if _terminal_mentioned_in_source(terminal_text, content):
                terminal_hits.add(terminal)
        query_overlap = _query_source_overlap(query_tokens, source_tokens)
        terminal_coverage = len(terminal_hits) / max(len(terminals), 1)
        support_score = support / max_support
        node_score = source_node_score[source_id] / max_node_score if max_node_score else 0.0
        length_penalty = min(len(source_tokens) / 512.0, 2.0)
        rerank_score = (
            query_param.swhc_source_support_weight * support_score
            + query_param.swhc_source_query_weight * query_overlap
            + query_param.swhc_source_terminal_weight * terminal_coverage
            + query_param.swhc_source_node_weight * node_score
            - query_param.swhc_source_length_penalty * length_penalty
        )
        text_units.append(
            {
                "id": source_id,
                "support": support,
                "content": content,
                "chunk_order_index": chunk_data.get("chunk_order_index", 0),
                "rerank_score": rerank_score,
                "query_overlap": query_overlap,
                "terminal_coverage": terminal_coverage,
            }
        )

    if query_param.swhc_source_rerank:
        text_units.sort(
            key=lambda item: (
                -item["rerank_score"],
                -item["support"],
                -item["query_overlap"],
                -item["terminal_coverage"],
                item["chunk_order_index"],
                item["id"],
            )
        )
    else:
        text_units.sort(
            key=lambda item: (-item["support"], item["chunk_order_index"], item["id"])
        )
    text_units = truncate_list_by_token_size(
        text_units,
        key=lambda item: item["content"],
        max_token_size=query_param.max_token_for_text_unit,
    )

    text_units_section_list = [["id", "content"]]
    for index, item in enumerate(text_units):
        text_units_section_list.append([index, item["content"]])
    text_units_context = list_of_list_to_csv(text_units_section_list)

    logger.info(
        "SWHC query uses %s entities, %s relations, %s text units",
        len(entity_nodes),
        len(hyperedge_nodes),
        len(text_units),
    )
    return entities_context, relations_context, text_units_context
