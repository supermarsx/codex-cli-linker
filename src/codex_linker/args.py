from __future__ import annotations
import argparse
import sys
from typing import List, Optional
import argparse as _argparse


def _default_base_for_provider_id(pid: str) -> str:
    try:
        from .spec import (
            DEFAULT_LMSTUDIO,
            DEFAULT_OLLAMA,
            DEFAULT_VLLM,
            DEFAULT_TGWUI,
            DEFAULT_TGI_8080,
            DEFAULT_OPENROUTER_LOCAL,
            DEFAULT_OPENROUTER,
            DEFAULT_ANTHROPIC,
            DEFAULT_GROQ,
            DEFAULT_MISTRAL,
            DEFAULT_DEEPSEEK,
            DEFAULT_COHERE,
            DEFAULT_BASETEN,
            DEFAULT_KOBOLDCPP,
            DEFAULT_ANYTHINGLLM,
            DEFAULT_JAN,
            DEFAULT_LLAMACPP,
            DEFAULT_OPENAI,
        )
        mapping = {
            "lmstudio": DEFAULT_LMSTUDIO,
            "ollama": DEFAULT_OLLAMA,
            "vllm": DEFAULT_VLLM,
            "tgwui": DEFAULT_TGWUI,
            "tgi": DEFAULT_TGI_8080,
            "openrouter": DEFAULT_OPENROUTER_LOCAL,
            "openrouter-remote": DEFAULT_OPENROUTER,
            "anthropic": DEFAULT_ANTHROPIC,
            "groq": DEFAULT_GROQ,
            "mistral": DEFAULT_MISTRAL,
            "deepseek": DEFAULT_DEEPSEEK,
            "cohere": DEFAULT_COHERE,
            "baseten": DEFAULT_BASETEN,
            "koboldcpp": DEFAULT_KOBOLDCPP,
            "anythingllm": DEFAULT_ANYTHINGLLM,
            "jan": DEFAULT_JAN,
            "llamacpp": DEFAULT_LLAMACPP,
            "openai": DEFAULT_OPENAI,
        }
        return mapping.get((pid or "").lower(), "")
    except Exception:
        return ""


class SetProviderAction(_argparse.Action):
    def __init__(self, option_strings, dest, nargs=0, **kwargs):
        self.provider_id = kwargs.pop("provider_id", None)
        self.set_auth = kwargs.pop("set_auth", None)
        self.use_default_base = kwargs.pop("use_default_base", True)
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # Set provider id
        setattr(namespace, "provider", self.provider_id)
        # Optional: set preferred auth method
        if self.set_auth:
            setattr(namespace, "preferred_auth_method", self.set_auth)
        # Only set base if not already provided and default exists
        try:
            base = getattr(namespace, "base_url", None)
        except Exception:
            base = None
        if (not base) and self.use_default_base:
            default_base = _default_base_for_provider_id(self.provider_id or "")
            if default_base:
                setattr(namespace, "base_url", default_base)
        # Mark flag present (dest is the flag name)
        setattr(namespace, self.dest, True)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments, tracking which were explicitly provided."""
    epilog = (
        "Shortcuts:\n"
        "  Providers: -oa/--openai, -oA/--openai-api, -og/--openai-gpt, -ls/--lmstudio, -ol/--ollama, -vl/--vllm, -tg/--tgwui, -ti/--tgi,\n"
        "             -or/--openrouter, -an/--anthropic, -gq/--groq, -mi/--mistral, -ds/--deepseek, -ch/--cohere, -bt/--baseten, -al/--anythingllm, -jn/--jan, -lc/--llamacpp, -kb/--koboldcpp\n"
        "  Guided: --guided (start guided pipeline), --no-emojis (hide emojis).\n"
    )
    p = argparse.ArgumentParser(
        description="Codex CLI Linker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=epilog,
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
    # Preset convenience flags
    # Provider presets with neat, direct actions
    # Local engines
    providers.add_argument("-ls", "--lmstudio", action=SetProviderAction, provider_id="lmstudio", help="Preset: LM Studio")
    providers.add_argument("-ol", "--ollama", action=SetProviderAction, provider_id="ollama", help="Preset: Ollama")
    providers.add_argument("-vl", "--vllm", action=SetProviderAction, provider_id="vllm", help="Preset: vLLM")
    providers.add_argument("-tg", "--tgwui", action=SetProviderAction, provider_id="tgwui", help="Preset: Text-Gen WebUI OpenAI plugin")
    providers.add_argument("-ti", "--tgi", action=SetProviderAction, provider_id="tgi", help="Preset: TGI shim on :8080")

    # Hosted / third-party
    providers.add_argument("-or", "--openrouter", action=SetProviderAction, provider_id="openrouter-remote", help="Preset: OpenRouter")
    providers.add_argument("-an", "--anthropic", action=SetProviderAction, provider_id="anthropic", help="Preset: Anthropic")
    providers.add_argument("-az", "--azure", action=SetProviderAction, provider_id="azure", help="Preset: Azure OpenAI")
    providers.add_argument("-gq", "--groq", action=SetProviderAction, provider_id="groq", help="Preset: Groq")
    providers.add_argument("-mi", "--mistral", action=SetProviderAction, provider_id="mistral", help="Preset: Mistral")
    providers.add_argument("-ds", "--deepseek", action=SetProviderAction, provider_id="deepseek", help="Preset: DeepSeek")
    providers.add_argument("-ch", "--cohere", action=SetProviderAction, provider_id="cohere", help="Preset: Cohere")
    providers.add_argument("-bt", "--baseten", action=SetProviderAction, provider_id="baseten", help="Preset: Baseten")
    providers.add_argument("-al", "--anythingllm", action=SetProviderAction, provider_id="anythingllm", help="Preset: AnythingLLM")
    providers.add_argument("-jn", "--jan", action=SetProviderAction, provider_id="jan", help="Preset: Jan AI")
    providers.add_argument("-lc", "--llamacpp", action=SetProviderAction, provider_id="llamacpp", help="Preset: llama.cpp")
    providers.add_argument("-kb", "--koboldcpp", action=SetProviderAction, provider_id="koboldcpp", help="Preset: KoboldCpp")
    providers.add_argument(
        "--azure-resource", help="Azure resource name (e.g., myresource)"
    )
    providers.add_argument("--azure-path", help="Azure path (e.g., openai/v1)")
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
        "-wa",
        "--wire-api",
        default="chat",
        choices=["chat", "responses"],
        help="Provider wire protocol",
    )
    providers.add_argument(
        "-Hh",
        "--http-header",
        action="append",
        default=[],
        help="Static HTTP header (KEY=VAL). Repeat for multiple.",
    )
    providers.add_argument(
        "-He",
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

    # MCP servers
    mcp.add_argument(
        "-mm",
        "--manage-mcp",
        action="store_true",
        help="Interactive: add/remove/edit mcp_servers entries before writing",
    )
    mcp.add_argument(
        "-mj",
        "--mcp-json",
        help="JSON object for mcp_servers (e.g., '{"
        "srv"
        ": {"
        "command"
        ": "
        "npx"
        ", "
        "args"
        ": ["
        "-y"
        ", "
        "mcp-server"
        "], "
        "env"
        ": {"
        "API_KEY"
        ": "
        "v"
        "}}}')",
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
    # Back-compat deprecated flags
    profiles.add_argument(
        "--enable-response-storage",
        action="store_false",
        dest="disable_response_storage",
        help=argparse.SUPPRESS,
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
        help=argparse.SUPPRESS,
    )
    profiles.add_argument(
        "-N",
        "--history-max-bytes",
        type=int,
        default=0,
        help="Maximum history size in bytes (0 uses default)",
    )
    profiles.add_argument(
        "-Wr",
        "--writable-roots",
        help="Comma-separated extra writable roots for sandbox_workspace_write",
    )
    profiles.add_argument(
        "-Nt",
        "--notify",
        help="Notification program (CSV or JSON array). Example: 'notify-send,Title,Body'",
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
        "-db",
        "--delete-all-backups",
        action="store_true",
        help="Remove all *.bak files under CODEX_HOME",
    )
    backups.add_argument(
        "-dc",
        "--confirm-delete-backups",
        action="store_true",
        help="Actually delete backups when --delete-all-backups is used",
    )
    backups.add_argument(
        "-rc",
        "--remove-config",
        action="store_true",
        help="Backup and remove existing config files",
    )
    backups.add_argument(
        "-rN",
        "--remove-config-no-bak",
        action="store_true",
        help="Remove config files without creating backups",
    )

    # Keys
    keys.add_argument(
        "-sK",
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

    # Other
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

    if argv is None:
        argv = sys.argv[1:]
    ns = p.parse_args(argv)
    # Initialize mcp servers container
    ns.mcp_servers = {}
    # Initialize per-profile overrides container (interactive-only)
    ns.profile_overrides = {}
    if getattr(ns, "mcp_json", None):
        try:
            import json

            data = json.loads(ns.mcp_json)
            if isinstance(data, dict):
                ns.mcp_servers = data
        except Exception:
            pass
    # Azure resource/path can synthesize base URL when given
    if getattr(ns, "azure", False):
        if getattr(ns, "azure_resource", None) or getattr(ns, "azure_path", None):
            res = getattr(ns, "azure_resource", "") or ""
            path = getattr(ns, "azure_path", "openai/v1") or "openai/v1"
            if res and not getattr(ns, "base_url", None):
                ns.base_url = f"https://{res}.openai.azure.com/{path}"
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
    # True when invoked without any CLI arguments
    ns._no_args = len(argv) == 0
    return ns


__all__ = ["parse_args"]
