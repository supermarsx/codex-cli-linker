"""Detection and model listing facade.

Thin wrapper around the monolithic implementation to enable incremental split.
"""

from .impl import (
    detect_base_url,
    list_models,
    try_auto_context_window,
)

__all__ = [
    "detect_base_url",
    "list_models",
    "try_auto_context_window",
]
