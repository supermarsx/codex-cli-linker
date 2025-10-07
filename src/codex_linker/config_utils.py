"""Helpers for merging remote defaults and applying saved state.

These utilities keep configuration sources consistent and predictable:
 - ``merge_config_defaults`` optionally fetches a small JSON document from a
   URL and applies values to CLI args only where the user did not specify a
   value (compared against a defaults Namespace).
 - ``apply_saved_state`` copies persisted preferences from ``LinkerState``
   into the current args where the user has not provided overrides.

Design notes
 - Avoids third‑party deps; uses the lightweight ``http_get_json`` helper.
 - Honors the ``args._explicit`` set when present to detect user‑provided
   options across argset modules.
"""

from __future__ import annotations
import argparse

from .state import LinkerState
from .ui import warn
from .utils import http_get_json


def merge_config_defaults(
    args: argparse.Namespace, defaults: argparse.Namespace
) -> None:
    """Merge remote JSON defaults into ``args`` for unspecified options.

    Parameters
    - ``args``: The live argument Namespace to update in-place.
    - ``defaults``: A Namespace representing parser defaults for comparison.

    Behavior
    - When ``args.config_url`` is set, fetches JSON and copies top-level keys
      into ``args`` only when ``args.<key> == defaults.<key>`` (i.e., option
      not set by user or other sources). If ``args._explicit`` is present,
      adds the key to it for traceability.
    - Logs a warning on fetch/parse failure; otherwise silent.
    """
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
    """Apply saved preferences for UX fields when not explicitly set.

    Parameters
    - ``args``: Live argument Namespace updated in-place.
    - ``defaults``: Parser defaults Namespace to detect unspecified values.
    - ``state``: Persisted non-secret preferences from prior runs.

    Fields considered
    - ``approval_policy``, ``sandbox_mode``, ``reasoning_effort``,
      ``reasoning_summary``, ``verbosity``, ``disable_response_storage``,
      ``no_history``, ``history_max_bytes``.

    Behavior
    - Skips fields in ``args._explicit`` (when present) or when ``args.<field>``
      differs from ``defaults.<field>``.
    """
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
            val = getattr(state, fld)
            if val:
                setattr(args, fld, val)


# =============== Main flow ===============

__all__ = ["merge_config_defaults", "apply_saved_state"]
