"""Helpers for reading SWHC debug traces."""

from __future__ import annotations

from typing import Any


def summarize_debug(debug: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary of the standard SWHC debug payload."""

    return {
        "terminal_count": len(debug.get("terminals", [])),
        "candidate_nodes": debug.get("candidate_nodes", 0),
        "candidate_edges": debug.get("candidate_edges", 0),
        "selected_node_count": len(debug.get("selected_nodes", [])),
        "bridge_path_count": len(debug.get("added_bridge_paths", [])),
        "objective": debug.get("objective", {}),
    }

