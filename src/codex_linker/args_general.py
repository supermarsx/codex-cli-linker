"""Argument definitions: General flags and core behavior.

This module groups general, cross-cutting flags that control overall runtime
behavior, discovery, banner, updates, etc. It is imported by args.parse_args
to keep the top-level file concise.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_general_args(p: argparse.ArgumentParser) -> None:
    """Attach general arguments to the parser.

    The options here match the previous implementation exactly to preserve
    behavior and compatibility with existing docs/tests.
    """
    # If '--version' is present, assume general has already been attached
    if _has_option(p, "--version"):
        return
    general = p.add_argument_group("General")
    general.add_argument(
        "-a",
        "--auto",
        action="store_true",
        help="Auto-detect base URL and skip that prompt",
    )
    general.add_argument(
        "-A",
        "--full-auto",
        action="store_true",
        help="Imply --auto and pick the first model with no prompts",
    )
    general.add_argument(
        "-L",
        "--launch",
        action="store_true",
        help="(No-op) Auto launch disabled by design",
    )
    general.add_argument(
        "-Q",
        "--yes",
        action="store_true",
        help="Assume defaults and suppress prompts when inputs are sufficient",
    )
    general.add_argument(
        "-v", "--verbose", action="store_true", help="Enable INFO/DEBUG logging"
    )
    general.add_argument(
        "-ll",
        "--log-level",
        "--level",
        choices=["debug", "info", "warning", "error"],
        help="Explicit log level (overrides --verbose)",
    )
    general.add_argument("-f", "--log-file", help="Write logs to a file")
    general.add_argument(
        "-J", "--log-json", action="store_true", help="Also log JSON to stdout"
    )
    general.add_argument("-R", "--log-remote", help="POST logs to this HTTP URL")
    general.add_argument(
        "-b",
        "--base-url",
        help="Explicit base URL (e.g., http://localhost:1234/v1)",
    )
    # Common OpenAI shortcuts pinned in General for discoverability
    try:
        from .args_providers import SetProviderAction  # local import to avoid cycles
    except Exception:
        from .argsets import SetProviderAction  # type: ignore
    general.add_argument(
        "-oa",
        "--openai",
        action=SetProviderAction,
        provider_id="openai",
        help="Shortcut: target OpenAI defaults (equivalent to --provider openai)",
    )
    general.add_argument(
        "-oA",
        "--openai-api",
        action=SetProviderAction,
        provider_id="openai",
        set_auth="apikey",
        help="OpenAI (API key auth): implies --provider openai and preferred_auth_method=apikey",
    )
    general.add_argument(
        "-og",
        "--openai-gpt",
        action=SetProviderAction,
        provider_id="openai",
        set_auth="chatgpt",
        help="OpenAI (ChatGPT auth): implies --provider openai and preferred_auth_method=chatgpt",
    )
    general.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print config(s) to stdout without writing files",
    )
    general.add_argument(
        "-V", "--version", action="store_true", help="Print version and exit"
    )
    general.add_argument(
        "-dr",
        "--doctor",
        action="store_true",
        help="Run preflight diagnostics (connectivity, permissions), then exit",
    )
    general.add_argument(
        "-cu",
        "--check-updates",
        action="store_true",
        help="Check for new releases on GitHub and PyPI, then exit",
    )
    general.add_argument(
        "-nuc",
        "--no-update-check",
        action="store_true",
        help="Skip automatic update checks",
    )
    general.add_argument(
        "-F",
        "--clear",
        action="store_true",
        help="Force clear screen and show banner on start (Windows default is off)",
    )
    general.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the ASCII banner at startup",
    )
    general.add_argument(
        "--guided",
        action="store_true",
        help="Start directly in the guided pipeline (step-by-step interactive)",
    )


__all__ = ["add_general_args"]
