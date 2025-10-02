"""Argument definitions: File management and outputs.

This module includes flags for diff/dry-run helpers and alternative formats,
state file overrides, and project-doc reading limits.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_file_mgmt_args(p: argparse.ArgumentParser) -> None:
    """Attach file/output management arguments to the parser."""
    if _has_option(p, "-Z"):
        return
    file_mgmt = p.add_argument_group("File management")
    file_mgmt.add_argument(
        "-Z",
        "--diff",
        action="store_true",
        help="With --dry-run, show a unified diff vs existing files",
    )
    file_mgmt.add_argument(
        "-j", "--json", action="store_true", help="Also write config.json"
    )
    file_mgmt.add_argument(
        "-y", "--yaml", action="store_true", help="Also write config.yaml"
    )
    file_mgmt.add_argument(
        "-x",
        "--state-file",
        help="Path to linker state JSON (default: $CODEX_HOME/linker_config.json)",
    )
    file_mgmt.add_argument(
        "-ws",
        "--workspace-state",
        action="store_true",
        help="Use .codex-linker.json in the current directory for state (overrides CODEX_HOME)",
    )
    file_mgmt.add_argument(
        "-oc",
        "--open-config",
        action="store_true",
        help="After writing files, print a command to open config.toml in the selected editor (no auto-launch)",
    )
    file_mgmt.add_argument(
        "-D",
        "--project-doc-max-bytes",
        type=int,
        default=1048576,
        help="Max bytes to read from project docs",
    )


__all__ = ["add_file_mgmt_args"]
