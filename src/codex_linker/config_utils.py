from __future__ import annotations
import argparse

from .state import LinkerState
from .ui import warn
from .utils import http_get_json


def merge_config_defaults(
    args: argparse.Namespace, defaults: argparse.Namespace
) -> None:
    """Merge values from a remote JSON file into ``args`` when unspecified."""
    if not getattr(args, "config_url", None):
        return
    data, err = http_get_json(args.config_url)
    if not data or not isinstance(data, dict):
        warn(f"Failed to fetch config defaults from {args.config_url}: {err}")
        return
    for k, v in data.items():
        if hasattr(args, k) and getattr(args, k) == getattr(defaults, k):
            setattr(args, k, v)
            if hasattr(args, "_explicit"):
                args._explicit.add(k)


def apply_saved_state(
    args: argparse.Namespace, defaults: argparse.Namespace, state: LinkerState
) -> None:
    """Apply saved preferences unless the user explicitly provided overrides."""
    specified: set[str] = getattr(args, "_explicit", set())
    for fld in (
        "approval_policy",
        "sandbox_mode",
        "reasoning_effort",
        "reasoning_summary",
        "verbosity",
        "disable_response_storage",
        "no_history",
        "history_max_bytes",
    ):
        if fld not in specified and getattr(args, fld) == getattr(defaults, fld):
            setattr(args, fld, getattr(state, fld))


# =============== Main flow ===============

__all__ = ["merge_config_defaults", "apply_saved_state"]
