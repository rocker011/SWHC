import asyncio
import unittest

from swhc import QueryParam
from swhc.core.solver import solve_swhc
from swhc.core.export import format_swhc_context


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
            "H1": {
                "role": "hyperedge",
                "weight": 4.0,
                "source_id": "c1",
            },
            "H2": {
                "role": "hyperedge",
                "weight": 4.0,
                "source_id": "c2",
            },
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


class SWHCTinyGraphTests(unittest.TestCase):
    def test_swhc_tiny_graph_selects_connector_and_exports_context(self):
        async def run():
            graph = TinyGraphStorage()
            chunks = TinyChunkStorage()
            params = QueryParam(
                only_need_context=True,
                subgraph_selector="swhc",
                swhc_candidate_hops=2,
                swhc_seed_topk_entity=2,
                swhc_seed_topk_hyperedge=2,
                swhc_hard_terminal_topk=3,
                swhc_budget_nodes=8,
            )
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
            self.assertGreaterEqual(result.subgraph.number_of_nodes(), 3)
            self.assertLessEqual(set(result.debug["terminals"]), set(result.subgraph.nodes))

            entities, relationships, sources = await format_swhc_context(
                result,
                chunks,
                params,
                query_text="Were Scott Derrickson and Ed Wood American?",
            )
            self.assertIn("Scott Derrickson", entities)
            self.assertIn("American filmmaker", sources)
            self.assertIn("hyperedge", relationships)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
