"""Argument definitions: Miscellaneous and UI-related flags.

This module covers TUI preferences, emojis, continuous display behavior, and
keys/keychain storage options.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_other_args(p: argparse.ArgumentParser) -> None:
    """Attach miscellaneous TUI and keychain arguments to the parser.

    Includes TUI style and notifications, emoji toggle, continuous display
    mode, and key-related options (set/openai-key, api key value, env key
    name, keychain backend selection).
    """
    if _has_option(p, "-T"):
        return
    other = p.add_argument_group("Other")
    other.add_argument(
        "-T", "--tui", default="table", help="TUI style for interactive prompts"
    )
    other.add_argument(
        "-Tn",
        "--tui-notifications",
        dest="tui_notifications",
        action="store_true",
        default=None,
        help="Enable TUI desktop notifications",
    )
    other.add_argument(
        "-Tt",
        "--tui-notification-types",
        help="Comma-separated notification types (agent-turn-complete,approval-requested)",
    )
    other.add_argument(
        "--no-emojis",
        action="store_true",
        help="Disable emojis in interactive menus and prompts",
    )
    other.add_argument(
        "--continuous",
        "--continous",
        dest="continuous",
        action="store_true",
        help="Keep interactive output on screen (disable auto-clear between steps)",
    )

    # Keys and keychain options
    keys = p.add_argument_group("Keys")
    keys.add_argument(
        "-sK",
        "--set-openai-key",
        action="store_true",
        help="Unique mode: prompt for or use --api-key to set OPENAI_API_KEY, then exit",
    )
    keys.add_argument(
        "-k",
        "--api-key",
        help="API key value for selected provider (stored in OS keychain if requested)",
    )
    keys.add_argument(
        "-E",
        "--env-key-name",
        dest="env_key_name",
        default="NULLKEY",
        help="Environment variable name used to read API key (per provider)",
    )
    keys.add_argument(
        "-kc",
        "--keychain",
        choices=[
            "none",
            "auto",
            "macos",
            "dpapi",
            "secretstorage",
            "secretservice",
            "pass",
            "bitwarden",
            "bw",
            "bitwarden-cli",
            "1password",
            "1passwd",
            "op",
        ],
        default="none",
        help="Optionally store --api-key in an OS keychain (never required)",
    )


__all__ = ["add_other_args"]
