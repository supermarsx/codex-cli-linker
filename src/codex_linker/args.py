from __future__ import annotations
import argparse
import sys
from typing import List, Optional

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments, tracking which were explicitly provided."""
    p = argparse.ArgumentParser(
        description="Codex ⇄ LM Studio / Ollama Linker (Config‑spec compliant)"
    )
    p.formatter_class = argparse.ArgumentDefaultsHelpFormatter
    p.add_argument(
        "-a",
        "--auto",
        action="store_true",
        help="Auto-detect base URL and skip that prompt",
    )
    p.add_argument(
        "-A",
        "--full-auto",
        action="store_true",
        help="Imply --auto and pick the first model with no prompts",
    )
    p.add_argument(
        "-L",
        "--launch",
        action="store_true",
        help="(No-op) Auto launch disabled by design",
    )
    p.add_argument(
        "-Z",
        "--diff",
        action="store_true",
        help="With --dry-run, show a unified diff vs existing files",
    )
    p.add_argument(
        "-Q",
        "--yes",
        action="store_true",
        help="Assume defaults and suppress prompts when inputs are sufficient",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Enable INFO/DEBUG logging"
    )
    p.add_argument(
        "--log-level",
        "--level",
        choices=["debug", "info", "warning", "error"],
        help="Explicit log level (overrides --verbose)",
    )
    p.add_argument("-f", "--log-file", help="Write logs to a file")
    p.add_argument(
        "-J", "--log-json", action="store_true", help="Also log JSON to stdout"
    )
    p.add_argument("-R", "--log-remote", help="POST logs to this HTTP URL")
    p.add_argument(
        "--keychain",
        choices=["none", "auto", "macos", "dpapi", "secretstorage"],
        default="none",
        help="Optionally store --api-key in an OS keychain (never required)",
    )
    p.add_argument(
        "-b", "--base-url", help="Explicit base URL (e.g., http://localhost:1234/v1)"
    )
    p.add_argument("-m", "--model", help="Model id to use (skip model picker)")
    p.add_argument(
        "-P", "--provider", help="Provider id (model_providers.<id>), default deduced"
    )
    p.add_argument(
        "-l",
        "--providers",
        help="Comma-separated provider ids to add (e.g., lmstudio,ollama)",
    )
    p.add_argument("-p", "--profile", help="Profile name, default deduced")
    p.add_argument("-k", "--api-key", help="API key to stash in env (dummy is fine)")
    p.add_argument(
        "-E",
        "--env-key-name",
        default="NULLKEY",
        help="Env var name that holds the API key (default: NULLKEY)",
    )
    p.add_argument("-c", "--config-url", help="URL to JSON file with default args")
    p.add_argument(
        "-i",
        "--model-index",
        type=int,
        help="When auto-selecting, index into the models list (default 0)",
    )
    # Custom linker state file path
    p.add_argument(
        "-x",
        "--state-file",
        help="Path to linker state JSON (default: $CODEX_HOME/linker_config.json)",
    )

    p.add_argument(
        "--delete-all-backups",
        action="store_true",
        help="Remove all *.bak files under CODEX_HOME",
    )
    p.add_argument(
        "--confirm-delete-backups",
        action="store_true",
        help="Actually delete backups when --delete-all-backups is used",
    )

    # Config tuning per # Config (choices restricted to spec)
    p.add_argument(
        "-q",
        "--approval-policy",
        default="on-failure",
        choices=["untrusted", "on-failure"],
        help="When to prompt for command approval (spec)",
    )
    p.add_argument(
        "-s",
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write"],
        help="OS sandbox policy (spec)",
    )
    p.add_argument(
        "-o",
        "--file-opener",
        default="vscode",
        choices=["vscode", "vscode-insiders"],
        help="File opener (spec)",
    )
    p.add_argument(
        "-r",
        "--reasoning-effort",
        default="low",
        choices=["minimal", "low"],
        help="model_reasoning_effort (spec)",
    )
    p.add_argument(
        "-u",
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise"],
        help="model_reasoning_summary (spec)",
    )
    p.add_argument(
        "-B",
        "--verbosity",
        default="medium",
        choices=["low", "medium"],
        help="model_verbosity (spec)",
    )
    p.add_argument(
        "-d",
        "--disable-response-storage",
        action="store_true",
        dest="disable_response_storage",
        help="Set disable_response_storage=true (e.g., ZDR orgs)",
    )
    p.add_argument(
        "--enable-response-storage",
        action="store_false",
        dest="disable_response_storage",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "-H",
        "--no-history",
        action="store_true",
        dest="no_history",
        help="Set history.persistence=none",
    )
    p.add_argument(
        "--history", action="store_false", dest="no_history", help=argparse.SUPPRESS
    )
    p.add_argument(
        "-z",
        "--azure-api-version",
        help="If targeting Azure, set query_params.api-version",
    )

    # Numeric knobs & misc
    p.add_argument(
        "-w",
        "--model-context-window",
        type=int,
        default=0,
        help="Context window tokens",
    )
    p.add_argument(
        "-t", "--model-max-output-tokens", type=int, default=0, help="Max output tokens"
    )
    p.add_argument("-D", "--project-doc-max-bytes", type=int, default=1048576)
    p.add_argument("-T", "--tui", default="table")
    p.add_argument("-g", "--hide-agent-reasoning", action="store_true")
    p.add_argument("-G", "--show-raw-agent-reasoning", action="store_true")
    p.add_argument("-Y", "--model-supports-reasoning-summaries", action="store_true")
    p.add_argument("-C", "--chatgpt-base-url", default="")
    p.add_argument("-U", "--experimental-resume", default="")
    p.add_argument("-I", "--experimental-instructions-file", default="")
    p.add_argument("-X", "--experimental-use-exec-command-tool", action="store_true")
    p.add_argument("-O", "--responses-originator-header-internal-override", default="")
    p.add_argument(
        "-M",
        "--preferred-auth-method",
        default="apikey",
        choices=["chatgpt", "apikey"],
    )
    p.add_argument("-W", "--tools-web-search", action="store_true")
    p.add_argument("-N", "--history-max-bytes", type=int, default=0)

    # Per‑provider network knobs
    p.add_argument("-K", "--request-max-retries", type=int, default=4)
    p.add_argument("-S", "--stream-max-retries", type=int, default=10)
    p.add_argument("-e", "--stream-idle-timeout-ms", type=int, default=300_000)

    # Output format toggles (TOML always written unless --dry-run; JSON/YAML only if explicitly requested)
    p.add_argument("-j", "--json", action="store_true", help="Also write config.json")
    p.add_argument("-y", "--yaml", action="store_true", help="Also write config.yaml")
    p.add_argument(
        "-F",
        "--clear",
        action="store_true",
        help="Force clear screen and show banner on start (Windows default is off)",
    )
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print config(s) to stdout without writing files",
    )
    p.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Print version and exit",
    )

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
