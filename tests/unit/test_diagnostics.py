import unittest

from swhc.diagnostics.debug_trace import summarize_debug
from swhc.diagnostics.evidence_audit import normalized_contains


class DiagnosticsTests(unittest.TestCase):
    def test_summarize_debug_counts_standard_fields(self):
        summary = summarize_debug(
            {
                "terminals": ["a", "b"],
                "candidate_nodes": 5,
                "candidate_edges": 4,
                "selected_nodes": ["a", "x", "b"],
                "added_bridge_paths": [["a", "x", "b"]],
                "objective": {"total": 1.25},
            }
        )

        self.assertEqual(summary["terminal_count"], 2)
        self.assertEqual(summary["selected_node_count"], 3)
        self.assertEqual(summary["bridge_path_count"], 1)
        self.assertEqual(summary["objective"]["total"], 1.25)

    def test_normalized_contains_ignores_case_and_extra_space(self):
        self.assertTrue(normalized_contains("The Chief   of Protocol", "chief of protocol"))


if __name__ == "__main__":
    unittest.main()
