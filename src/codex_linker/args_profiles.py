"""Argument definitions: Profiles and config merging behavior.

This module contains flags to manage/merge profiles, and integrate remote
defaults via --config-url.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_profile_args(p: argparse.ArgumentParser) -> None:
    """Attach profile and merge-related arguments to the parser."""
    if _has_option(p, "-p"):
        return
    profiles = p.add_argument_group("Profiles")
    profiles.add_argument("-p", "--profile", help="Profile name, default deduced")
    profiles.add_argument(
        "-op",
        "--overwrite-profile",
        action="store_true",
        help="Allow overwriting an existing [profiles.<name>] in config.toml",
    )
    profiles.add_argument(
        "-mP",
        "--manage-profiles",
        action="store_true",
        help="Interactive: add/remove/edit profile entries before writing",
    )
    profiles.add_argument(
        "-mp",
        "--merge-profiles",
        action="store_true",
        help="Merge generated [profiles.*] into existing config.toml (preserve others)",
    )
    profiles.add_argument(
        "-mc",
        "--merge-config",
        action="store_true",
        help="Merge generated config into existing config.toml (append new sections, prompt on conflicts)",
    )
    profiles.add_argument(
        "-mO",
        "--merge-overwrite",
        action="store_true",
        help="When merging, overwrite conflicting sections/keys without prompting",
    )
    profiles.add_argument(
        "-c", "--config-url", help="URL to JSON file with default args"
    )
    # Sandbox/workspace-write tuning
    profiles.add_argument(
        "-Na",
        "--network-access",
        dest="network_access",
        action="store_true",
        default=None,
        help="Enable network_access under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "-Et",
        "--exclude-tmpdir-env-var",
        dest="exclude_tmpdir_env_var",
        action="store_true",
        default=None,
        help="Exclude $TMPDIR from writable roots under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "-Es",
        "--exclude-slash-tmp",
        dest="exclude_slash_tmp",
        action="store_true",
        default=None,
        help="Exclude /tmp from writable roots under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "-ES",
        "--no-exclude-slash-tmp",
        dest="exclude_slash_tmp",
        action="store_false",
        help="Include /tmp as writable under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "-Wr",
        "--writable-roots",
        help="Comma-separated extra writable roots for sandbox_workspace_write",
    )
    # UI/notify and misc profile-level fields
    profiles.add_argument(
        "-Nt",
        "--notify",
        help=(
            "Notification program (CSV or JSON array). Example: 'notify-send,Title,Body'"
        ),
    )
    profiles.add_argument(
        "-In",
        "--instructions",
        default="",
        help="Instructions string (currently ignored by Codex)",
    )
    profiles.add_argument(
        "-Tp",
        "--trust-project",
        action="append",
        default=[],
        help="Mark a project/worktree path as trusted (repeatable)",
    )
    # Experimental toggles
    profiles.add_argument(
        "-U",
        "--experimental-resume",
        default="",
        help="Experimental: resume session token",
    )
    profiles.add_argument(
        "-I",
        "--experimental-instructions-file",
        default="",
        help="Experimental: path to instructions file",
    )
    profiles.add_argument(
        "-X",
        "--experimental-use-exec-command-tool",
        action="store_true",
        help="Experimental: enable exec_command tool",
    )
    profiles.add_argument(
        "-O",
        "--responses-originator-header-internal-override",
        default="",
        help="Experimental: internal responses-originator header override",
    )
    profiles.add_argument(
        "-q",
        "--approval-policy",
        default="on-failure",
        choices=["never", "on-failure", "on-request", "always", "untrusted"],
        help="Agent approval policy (spec)",
    )
    profiles.add_argument(
        "-s",
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Filesystem sandbox mode (spec)",
    )
    profiles.add_argument(
        "-o",
        "--file-opener",
        default="vscode",
        help="Editor to suggest opening files (no auto-launch)",
    )
    profiles.add_argument(
        "--history",
        dest="no_history",
        action="store_false",
        help="Enable history (disables --no-history)",
    )
    profiles.add_argument(
        "--no-history",
        action="store_true",
        help="Disable history (saves none)",
    )
    profiles.add_argument(
        "--history-max-bytes",
        type=int,
        default=0,
        help="Max bytes for history persistence (0 means default)",
    )
    profiles.add_argument(
        "--enable-response-storage",
        dest="disable_response_storage",
        action="store_false",
        help="Enable response storage (default is on)",
    )
    profiles.add_argument(
        "--disable-response-storage",
        action="store_true",
        help="Disable response storage (for restricted environments)",
    )


__all__ = ["add_profile_args"]
