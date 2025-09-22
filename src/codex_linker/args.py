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
    mcp = p.add_argument_group("MCP servers")
    file_mgmt = p.add_argument_group("File management")
    other = p.add_argument_group("Other")

    # General
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
        "--openai",
        action="store_true",
        help="Shortcut: target OpenAI API defaults (equivalent to --provider openai)",
    )
    general.add_argument(
        "--openai-api",
        action="store_true",
        help="OpenAI (API key auth): implies --provider openai and preferred_auth_method=apikey",
    )
    general.add_argument(
        "--openai-gpt",
        action="store_true",
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
        "--doctor",
        action="store_true",
        help="Run preflight diagnostics (connectivity, permissions), then exit",
    )
    general.add_argument(
        "--check-updates",
        action="store_true",
        help="Check for new releases on GitHub and PyPI, then exit",
    )
    general.add_argument(
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
        choices=["minimal", "low", "medium", "high"],
        help="model_reasoning_effort (spec)",
    )
    model_opts.add_argument(
        "-u",
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise", "detailed", "none"],
        help="model_reasoning_summary (spec)",
    )
    model_opts.add_argument(
        "-B",
        "--verbosity",
        default="medium",
        choices=["low", "medium", "high"],
        help="model_verbosity (spec)",
    )
    model_opts.add_argument(
        "-g",
        "--hide-agent-reasoning",
        action="store_true",
        help="Hide agent reasoning messages",
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
        "-z",
        "--azure-api-version",
        help="If targeting Azure, set query_params.api-version",
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
        "--wire-api",
        default="chat",
        choices=["chat", "responses"],
        help="Provider wire protocol",
    )
    providers.add_argument(
        "--http-header",
        action="append",
        default=[],
        help="Static HTTP header (KEY=VAL). Repeat for multiple.",
    )
    providers.add_argument(
        "--env-http-header",
        action="append",
        default=[],
        help="Env-sourced HTTP header (KEY=ENV_VAR). Repeat for multiple.",
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
    profiles.add_argument(
        "--overwrite-profile",
        action="store_true",
        help="Allow overwriting an existing [profiles.<name>] in config.toml",
    )
    profiles.add_argument(
        "--manage-profiles",
        action="store_true",
        help="Interactive: add/remove/edit profile entries before writing",
    )
    profiles.add_argument(
        "--merge-profiles",
        action="store_true",
        help="Merge generated [profiles.*] into existing config.toml (preserve others)",
    )

    # MCP servers
    mcp.add_argument(
        "--manage-mcp",
        action="store_true",
        help="Interactive: add/remove/edit mcp_servers entries before writing",
    )
    mcp.add_argument(
        "--mcp-json",
        help="JSON object for mcp_servers (e.g., '{""srv"": {""command"": ""npx"", ""args"": [""-y"", ""mcp-server""], ""env"": {""API_KEY"": ""v""}}}')",
    )
    profiles.add_argument(
        "-c", "--config-url", help="URL to JSON file with default args"
    )
    profiles.add_argument(
        "-q",
        "--approval-policy",
        default="on-failure",
        choices=["untrusted", "on-failure", "on-request", "never"],
        help="When to prompt for command approval (spec)",
    )
    profiles.add_argument(
        "-s",
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="OS sandbox policy (spec)",
    )
    profiles.add_argument(
        "--network-access",
        dest="network_access",
        action="store_true",
        default=None,
        help="Enable network_access under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "--no-network-access",
        dest="network_access",
        action="store_false",
        help="Disable network_access under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "--exclude-tmpdir-env-var",
        dest="exclude_tmpdir_env_var",
        action="store_true",
        default=None,
        help="Exclude $TMPDIR from writable roots under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "--no-exclude-tmpdir-env-var",
        dest="exclude_tmpdir_env_var",
        action="store_false",
        help="Include $TMPDIR as writable under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "--exclude-slash-tmp",
        dest="exclude_slash_tmp",
        action="store_true",
        default=None,
        help="Exclude /tmp from writable roots under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "--no-exclude-slash-tmp",
        dest="exclude_slash_tmp",
        action="store_false",
        help="Include /tmp as writable under [sandbox_workspace_write]",
    )
    profiles.add_argument(
        "-o",
        "--file-opener",
        default="vscode",
        choices=["vscode", "vscode-insiders", "windsurf", "cursor", "none"],
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
        "--writable-roots",
        help="Comma-separated extra writable roots for sandbox_workspace_write",
    )
    profiles.add_argument(
        "--notify",
        help="Notification program (CSV or JSON array). Example: 'notify-send,Title,Body'",
    )
    profiles.add_argument(
        "--instructions",
        default="",
        help="Instructions string (currently ignored by Codex)",
    )
    profiles.add_argument(
        "--trust-project",
        action="append",
        default=[],
        help="Mark a project/worktree path as trusted (repeatable)",
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
    keys.add_argument(
        "--set-openai-key",
        action="store_true",
        help="Unique mode: prompt for or use --api-key to set OPENAI_API_KEY, then exit",
    )
    keys.add_argument("-k", "--api-key", help="API key to stash in env (dummy is fine)")
    keys.add_argument(
        "-E",
        "--env-key-name",
        default="NULLKEY",
        help="Env var name that holds the API key (default: NULLKEY)",
    )
    keys.add_argument(
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
        "--workspace-state",
        action="store_true",
        help="Use .codex-linker.json in the current directory for state (overrides CODEX_HOME)",
    )
    file_mgmt.add_argument(
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

    # Other
    other.add_argument(
        "-T", "--tui", default="table", help="TUI style for interactive prompts"
    )

    if argv is None:
        argv = sys.argv[1:]
    ns = p.parse_args(argv)
    # Initialize mcp servers container
    ns.mcp_servers = {}
    if getattr(ns, "mcp_json", None):
        try:
            import json

            data = json.loads(ns.mcp_json)
            if isinstance(data, dict):
                ns.mcp_servers = data
        except Exception:
            pass
    # Convenience: --openai implies --provider openai
    if getattr(ns, "openai", False) and not getattr(ns, "provider", None):
        ns.provider = "openai"
    # Convenience: --openai-api and --openai-gpt set provider and auth method
    if getattr(ns, "openai_api", False):
        ns.provider = "openai"
        ns.preferred_auth_method = "apikey"
    if getattr(ns, "openai_gpt", False):
        ns.provider = "openai"
        ns.preferred_auth_method = "chatgpt"
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
