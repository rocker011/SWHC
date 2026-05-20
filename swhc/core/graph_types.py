"""Shared graph-related type aliases for SWHC core code."""

from __future__ import annotations

from typing import Any, TypeAlias

NodeId: TypeAlias = str
NodeData: TypeAlias = dict[str, Any]
EdgeData: TypeAlias = dict[str, Any]
SeedRecord: TypeAlias = dict[str, Any]

