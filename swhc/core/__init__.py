"""Core SWHC API.

For the initial migration, these modules are thin facades over `swhc.legacy`.
Replace the internals here incrementally after parity checks pass.
"""

from .export import format_swhc_context
from .solver import solve_swhc

__all__ = ["format_swhc_context", "solve_swhc"]

