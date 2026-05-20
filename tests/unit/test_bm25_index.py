import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))
from evaluation.methods.common import BM25ChunkIndex


class BM25IndexTests(unittest.TestCase):
    def test_bm25_index_ranks_matching_chunk_first(self):
        index = BM25ChunkIndex.from_chunks(
            [
                {
                    "id": "c1",
                    "content": "Scott Derrickson directed Doctor Strange.",
                    "chunk_order_index": 0,
                },
                {
                    "id": "c2",
                    "content": "Ed Wood directed Plan 9 from Outer Space.",
                    "chunk_order_index": 1,
                },
            ]
        )

        hits = index.query("Who directed Doctor Strange?", top_k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "c1")


if __name__ == "__main__":
    unittest.main()
