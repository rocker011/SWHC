"""SWHC solver facade.

The current implementation delegates to the migrated HyperGraphRAG evaluation
code. This keeps the first project migration behavior-preserving.
"""

from __future__ import annotations

from swhc.legacy.swhc import (
    SWHCResult,
    _augment_connector_subgraph as augment_connector_subgraph,
    _initialize_connector_subgraph as initialize_connector_subgraph,
    _prune_connector_subgraph as prune_connector_subgraph,
    build_candidate_subgraph,
    solve_swhc,
)

__all__ = [
    "SWHCResult",
    "augment_connector_subgraph",
    "build_candidate_subgraph",
    "initialize_connector_subgraph",
    "prune_connector_subgraph",
    "solve_swhc",
]

