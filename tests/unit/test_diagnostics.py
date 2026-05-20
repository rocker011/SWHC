from swhc.diagnostics.debug_trace import summarize_debug
from swhc.diagnostics.evidence_audit import normalized_contains


def test_summarize_debug_counts_standard_fields():
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

    assert summary["terminal_count"] == 2
    assert summary["selected_node_count"] == 3
    assert summary["bridge_path_count"] == 1
    assert summary["objective"]["total"] == 1.25


def test_normalized_contains_ignores_case_and_extra_space():
    assert normalized_contains("The Chief   of Protocol", "chief of protocol")

