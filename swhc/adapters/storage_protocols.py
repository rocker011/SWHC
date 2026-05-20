"""Minimal storage protocols needed by SWHC.

These protocols describe what the SWHC solver needs from an upstream graph
index without tying the core method to a concrete HyperGraphRAG class.
"""

from __future__ import annotations

from typing import Any, Protocol


class GraphStorageProtocol(Protocol):
    async def get_node(self, node_id: str) -> dict[str, Any] | None: ...

    async def get_edge(self, source_id: str, target_id: str) -> dict[str, Any] | None: ...

    async def get_node_edges(self, node_id: str) -> list[tuple[str, str]] | None: ...


class ChunkStorageProtocol(Protocol):
    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None: ...

