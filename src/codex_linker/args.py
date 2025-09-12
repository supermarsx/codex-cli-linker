from __future__ import annotations
import argparse
import sys
from typing import List, Optional


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments, tracking which were explicitly provided."""
    p = argparse.ArgumentParser(
        description="Codex CLI Linker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    general = p.add_argument_group("General")
    model_opts = p.add_argument_group("Model options")
    providers = p.add_argument_group("Providers")
    profiles = p.add_argument_group("Profiles")
    backups = p.add_argument_group("Backups")
    keys = p.add_argument_group("Keys")
    file_mgmt = p.add_argument_group("File management")
    other = p.add_argument_group("Other")

    # General
    general.add_argument(
        "-a", "--auto", action="store_true", help="Auto-detect base URL and skip that prompt"
    )
    general.add_argument(
        "-A",
        "--full-auto",
        action="store_true",
        help="Imply --auto and pick the first model with no prompts",
    )
    general.add_argument(
        "-L", "--launch", action="store_true", help="(No-op) Auto launch disabled by design"
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
        "-F",
        "--clear",
        action="store_true",
        help="Force clear screen and show banner on start (Windows default is off)",
    )

    # Model options
    model_opts.add_argument("-m", "--model", help="Model id to use (skip model picker)")
    model_opts.add_argument(
        "-i",
        "--model-index",
        type=int,
        help="When auto-selecting, index into the models list (default 0)",
    )
    model_opts.add_argument(
        "-w",
        "--model-context-window",
        type=int,
        default=0,
        help="Context window tokens",
    )
    model_opts.add_argument(
        "-t", "--model-max-output-tokens", type=int, default=0, help="Max output tokens"
    )
    model_opts.add_argument(
        "-r",
        "--reasoning-effort",
        default="low",
        choices=["minimal", "low"],
        help="model_reasoning_effort (spec)",
    )
    model_opts.add_argument(
        "-u",
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise"],
        help="model_reasoning_summary (spec)",
    )
    model_opts.add_argument(
        "-B",
        "--verbosity",
        default="medium",
        choices=["low", "medium"],
        help="model_verbosity (spec)",
    )
    model_opts.add_argument(
        "-g", "--hide-agent-reasoning", action="store_true", help="Hide agent reasoning messages"
    )
    model_opts.add_argument(
        "-G",
        "--show-raw-agent-reasoning",
        action="store_true",
        help="Show raw agent reasoning messages",
    )
    model_opts.add_argument(
        "-Y",
        "--model-supports-reasoning-summaries",
        action="store_true",
        help="Indicate model supports reasoning summaries",
    )

    # Providers
    providers.add_argument(
        "-P",
        "--provider",
        help="Provider id (model_providers.<id>), default deduced",
    )
    providers.add_argument(
        "-l",
        "--providers",
        help="Comma-separated provider ids to add (e.g., lmstudio,ollama)",
    )
    providers.add_argument(
        "-z", "--azure-api-version", help="If targeting Azure, set query_params.api-version"
    )
    providers.add_argument(
        "-C",
        "--chatgpt-base-url",
        default="",
        help="Base URL override for ChatGPT provider",
    )
    providers.add_argument(
        "-M",
        "--preferred-auth-method",
        default="apikey",
        choices=["chatgpt", "apikey"],
        help="Preferred authentication method for provider",
    )
    providers.add_argument(
        "-W",
        "--tools-web-search",
        action="store_true",
        help="Enable web-search tool when supported",
    )
    providers.add_argument(
        "-K",
        "--request-max-retries",
        type=int,
        default=4,
        help="Max retries for initial API request",
    )
    providers.add_argument(
        "-S",
        "--stream-max-retries",
        type=int,
        default=10,
        help="Max retries for streaming responses",
    )
    providers.add_argument(
        "-e",
        "--stream-idle-timeout-ms",
        type=int,
        default=300_000,
        help="Stream idle timeout in milliseconds",
    )

    # Profiles
    profiles.add_argument("-p", "--profile", help="Profile name, default deduced")
    profiles.add_argument("-c", "--config-url", help="URL to JSON file with default args")
    profiles.add_argument(
        "-q",
        "--approval-policy",
        default="on-failure",
        choices=["untrusted", "on-failure"],
        help="When to prompt for command approval (spec)",
    )
    profiles.add_argument(
        "-s",
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write"],
        help="OS sandbox policy (spec)",
    )
    profiles.add_argument(
        "-o",
        "--file-opener",
        default="vscode",
        choices=["vscode", "vscode-insiders"],
        help="File opener (spec)",
    )
    profiles.add_argument(
        "-d",
        "--disable-response-storage",
        action="store_true",
        dest="disable_response_storage",
        help="Set disable_response_storage=true (e.g., ZDR orgs)",
    )
    profiles.add_argument(
        "--enable-response-storage",
        action="store_false",
        dest="disable_response_storage",
        help="Allow response storage",
    )
    profiles.add_argument(
        "-H",
        "--no-history",
        action="store_true",
        dest="no_history",
        help="Set history.persistence=none",
    )
    profiles.add_argument(
        "--history",
        action="store_false",
        dest="no_history",
        help="Enable history persistence",
    )
    profiles.add_argument(
        "-N",
        "--history-max-bytes",
        type=int,
        default=0,
        help="Maximum history size in bytes (0 uses default)",
    )
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

    # Backups
    backups.add_argument(
        "--delete-all-backups",
        action="store_true",
        help="Remove all *.bak files under CODEX_HOME",
    )
    backups.add_argument(
        "--confirm-delete-backups",
        action="store_true",
        help="Actually delete backups when --delete-all-backups is used",
    )
    backups.add_argument(
        "--remove-config",
        action="store_true",
        help="Backup and remove existing config files",
    )
    backups.add_argument(
        "--remove-config-no-bak",
        action="store_true",
        help="Remove config files without creating backups",
    )

    # Keys
    keys.add_argument("-k", "--api-key", help="API key to stash in env (dummy is fine)")
    keys.add_argument(
        "-E",
        "--env-key-name",
        default="NULLKEY",
        help="Env var name that holds the API key (default: NULLKEY)",
    )
    keys.add_argument(
        "--keychain",
        choices=["none", "auto", "macos", "dpapi", "secretstorage"],
        default="none",
        help="Optionally store --api-key in an OS keychain (never required)",
    )

    # File management
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
        "-D",
        "--project-doc-max-bytes",
        type=int,
        default=1048576,
        help="Max bytes to read from project docs",
    )

    # Other
    other.add_argument("-T", "--tui", default="table", help="TUI style for interactive prompts")

    if argv is None:
        argv = sys.argv[1:]
    ns = p.parse_args(argv)
    # Normalize providers list
    provs = []
    if getattr(ns, "providers", None):
        provs = [p.strip() for p in str(ns.providers).split(",") if p.strip()]
    ns.providers_list = provs
    ns._explicit = {
        a.dest
        for a in p._actions
        if any(
            opt in argv or any(arg.startswith(opt + "=") for arg in argv)
            for opt in a.option_strings
        )
    }
    return ns


__all__ = ["parse_args"]

