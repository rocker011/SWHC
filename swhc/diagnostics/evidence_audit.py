"""Evidence-audit utilities for future SWHC error analysis."""

from __future__ import annotations


def normalized_contains(text: str, needle: str) -> bool:
    """Case-insensitive whitespace-normalized containment check."""

    normalized_text = " ".join((text or "").lower().split())
    normalized_needle = " ".join((needle or "").lower().split())
    return bool(normalized_needle) and normalized_needle in normalized_text

