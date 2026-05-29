import asyncio
from pathlib import Path
import sys
import unittest

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))

from hypergraphrag.base import QueryParam
from hypergraphrag.operate import _build_query_context
from hypergraphrag.swhc import SWHCResult, format_swhc_context, format_swhc_context_v0


class TinyGraphStorage:
    def __init__(self):
        long_description = " ".join(["long evidence descriptor"] * 30)
        self.nodes = {
            "SCOTT DERRICKSON": {
                "role": "entity",
                "entity_type": "PERSON",
                "description": f"Scott Derrickson is an American filmmaker. {long_description}",
                "source_id": "c1",
            },
            "AMERICAN": {
                "role": "entity",
                "entity_type": "NATIONALITY",
                "description": f"American nationality connects both people. {long_description}",
                "source_id": "c1<SEP>c2",
            },
            "ED WOOD": {
                "role": "entity",
                "entity_type": "PERSON",
                "description": f"Ed Wood was an American filmmaker. {long_description}",
                "source_id": "c2",
            },
            "<hyperedge>SCOTT DERRICKSON NATIONALITY": {
                "role": "hyperedge",
                "weight": 4.0,
                "source_id": "c1",
            },
            "<hyperedge>ED WOOD NATIONALITY": {
                "role": "hyperedge",
                "weight": 4.0,
                "source_id": "c2",
            },
        }
        self.edges = {
            ("<hyperedge>SCOTT DERRICKSON NATIONALITY", "SCOTT DERRICKSON"): {
                "weight": 4.0,
                "source_id": "c1",
            },
            ("<hyperedge>SCOTT DERRICKSON NATIONALITY", "AMERICAN"): {
                "weight": 4.0,
                "source_id": "c1",
            },
            ("<hyperedge>ED WOOD NATIONALITY", "AMERICAN"): {
                "weight": 4.0,
                "source_id": "c2",
            },
            ("<hyperedge>ED WOOD NATIONALITY", "ED WOOD"): {
                "weight": 4.0,
                "source_id": "c2",
            },
        }

    async def get_node(self, node_id):
        return self.nodes.get(node_id)

    async def get_edge(self, left, right):
        return self.edges.get((left, right)) or self.edges.get((right, left))

    async def get_node_edges(self, node_id):
        return [edge for edge in self.edges if node_id in edge]

    async def node_degree(self, node_id):
        return sum(1 for edge in self.edges if node_id in edge)


class TinyChunkStorage:
    def __init__(self):
        self.chunks = {
            "c1": {
                "content": "Scott Derrickson is an American filmmaker and director.",
                "chunk_order_index": 0,
            },
            "c2": {
                "content": "Ed Wood was an American filmmaker, actor, and writer.",
                "chunk_order_index": 1,
            },
        }

    async def get_by_id(self, chunk_id):
        return self.chunks.get(chunk_id)


class TinyVectorStorage:
    def __init__(self, rows):
        self.rows = rows

    async def query(self, query, top_k):
        return self.rows[:top_k]


def build_result_graph() -> SWHCResult:
    storage = TinyGraphStorage()
    graph = nx.Graph()
    for node_id, node_data in storage.nodes.items():
        graph.add_node(node_id, **node_data)
    for (left, right), edge_data in storage.edges.items():
        graph.add_edge(left, right, **edge_data)
    graph.graph["node_scores"] = {
        "SCOTT DERRICKSON": 1.0,
        "AMERICAN": 0.8,
        "ED WOOD": 1.0,
        "<hyperedge>SCOTT DERRICKSON NATIONALITY": 0.9,
        "<hyperedge>ED WOOD NATIONALITY": 0.9,
    }
    return SWHCResult(
        subgraph=graph,
        debug={
            "terminals": ["SCOTT DERRICKSON", "ED WOOD"],
            "candidate_nodes": 5,
            "candidate_edges": 4,
            "selected_nodes": list(graph.nodes()),
            "added_bridge_paths": [],
            "objective": {"total": 0.0},
        },
    )


class SWHCV0ExportTests(unittest.TestCase):
    def test_legacy_variant_still_uses_legacy_export_shape(self):
        async def run():
            params = QueryParam(
                only_need_context=True,
                subgraph_selector="swhc",
                swhc_variant="legacy",
            )
            entities, relationships, sources = await format_swhc_context(
                build_result_graph(),
                TinyChunkStorage(),
                params,
                query_text="Were Scott Derrickson and Ed Wood American?",
            )
            self.assertIn("id,entity,type,description", entities)
            self.assertIn("id,hyperedge,related_entities", relationships)
            self.assertIn("id,content", sources)
            self.assertNotIn("supporting_sources", entities)

        asyncio.run(run())

    def test_v0_export_preserves_structure_and_adds_provenance(self):
        async def run():
            params = QueryParam(
                only_need_context=True,
                subgraph_selector="swhc",
                swhc_variant="v0",
                max_token_for_local_context=1,
                max_token_for_global_context=1,
                swhc_v0_evidence_topk=2,
                swhc_v0_evidence_max_tokens=200,
            )
            evidence, entities, relationships, sources = await format_swhc_context_v0(
                build_result_graph(),
                TinyChunkStorage(),
                params,
                query_text="Were Scott Derrickson and Ed Wood American?",
            )
            self.assertIn("Scott Derrickson", entities)
            self.assertIn("Ed Wood", entities)
            self.assertIn("<hyperedge>SCOTT DERRICKSON NATIONALITY", relationships)
            self.assertIn("<hyperedge>ED WOOD NATIONALITY", relationships)
            self.assertIn("supporting_sources", entities)
            self.assertIn("evidence_hint", relationships)
            self.assertIn("id,source_id,evidence", evidence)
            self.assertIn("id,source_id,content", sources)

        asyncio.run(run())

    def test_v0_full_context_order_is_stable(self):
        async def run():
            params = QueryParam(
                only_need_context=True,
                subgraph_selector="swhc",
                swhc_variant="v0",
                swhc_candidate_hops=2,
                swhc_seed_topk_entity=2,
                swhc_seed_topk_hyperedge=2,
                swhc_hard_terminal_topk=3,
                swhc_budget_nodes=8,
            )
            context = await _build_query_context(
                [
                    "SCOTT DERRICKSON, ED WOOD, AMERICAN",
                    "<hyperedge>SCOTT DERRICKSON ED WOOD NATIONALITY",
                ],
                TinyGraphStorage(),
                TinyVectorStorage(
                    [
                        {"entity_name": "SCOTT DERRICKSON", "distance": 0.95},
                        {"entity_name": "ED WOOD", "distance": 0.9},
                    ]
                ),
                TinyVectorStorage(
                    [
                        {
                            "hyperedge_name": "<hyperedge>SCOTT DERRICKSON NATIONALITY",
                            "distance": 0.95,
                        },
                        {
                            "hyperedge_name": "<hyperedge>ED WOOD NATIONALITY",
                            "distance": 0.9,
                        },
                    ]
                ),
                TinyChunkStorage(),
                params,
                original_query="Were Scott Derrickson and Ed Wood American?",
            )
            self.assertLess(
                context.index("-----Relevant Evidence-----"),
                context.index("-----Entities-----"),
            )
            self.assertLess(
                context.index("-----Entities-----"),
                context.index("-----Relationships-----"),
            )
            self.assertLess(
                context.index("-----Relationships-----"),
                context.index("-----Sources-----"),
            )
            self.assertIn("source_id", context)
            self.assertIn("Relevant Evidence", context)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
