"""HyperGraphRAG adapter placeholders.

The first migration keeps legacy code intact. This module is the future home for
adapter code that converts HyperGraphRAG storage objects into the narrower SWHC
protocols defined in `storage_protocols.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HyperGraphRAGStores:
    knowledge_graph: Any
    text_chunks: Any
    entities_vdb: Any | None = None
    hyperedges_vdb: Any | None = None

