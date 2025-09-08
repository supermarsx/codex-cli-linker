"""CLI facade for codex-cli-linker.

This minimal split keeps the single-file entry working while exposing
argparse/UI helpers from a dedicated module.
"""

# Re-export selected UI + CLI functions from the monolith for now
from .impl import (
    parse_args,
    configure_logging,
    merge_config_defaults,
    apply_saved_state,
    prompt_choice,
    prompt_yes_no,
    pick_base_url,
    banner,
    clear_screen,
    c,
    supports_color,
    info,
    ok,
    warn,
    err,
    LinkerState,
    main,
)

__all__ = [
    "parse_args",
    "configure_logging",
    "merge_config_defaults",
    "apply_saved_state",
    "prompt_choice",
    "prompt_yes_no",
    "pick_base_url",
    "banner",
    "clear_screen",
    "c",
    "supports_color",
    "info",
    "ok",
    "warn",
    "err",
    "LinkerState",
    "main",
]
