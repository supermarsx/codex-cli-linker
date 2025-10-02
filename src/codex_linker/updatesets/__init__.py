"""Aggregated update utilities split into small modules.

This package mirrors the argsets pattern: each module holds a cohesive part of
the update logic and these are re-exported for easy import.
"""

from __future__ import annotations

from .types import SourceResult, UpdateCheckResult
from .detect import detect_install_origin
from .sources import determine_update_sources
from .version import is_version_newer
from .check import check_for_updates, _normalize_sources, _save_cache, _load_cache, _FETCHERS
from .report import _log_update_sources, _report_update_status

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
