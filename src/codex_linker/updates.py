from __future__ import annotations

"""Thin facade over updatesets modules for backward compatibility.

This preserves the original public surface (function and type names) while the
implementation lives in ``src/codex_linker/updatesets/`` similar to how args
were modularized under argsets/.
"""

from .updatesets import (
    check_for_updates,
    determine_update_sources,
    detect_install_origin,
    is_version_newer,
    SourceResult,
    UpdateCheckResult,
    _log_update_sources,
    _report_update_status,
    _normalize_sources,
    _save_cache,
    _load_cache,
    _FETCHERS,
)

__all__ = [
    "check_for_updates",
    "determine_update_sources",
    "detect_install_origin",
    "is_version_newer",
    "SourceResult",
    "UpdateCheckResult",
    "_log_update_sources",
    "_report_update_status",
    "_normalize_sources",
    "_save_cache",
    "_load_cache",
    "_FETCHERS",
]
