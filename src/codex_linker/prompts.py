from __future__ import annotations

import inspect
import sys
import os
from typing import List, Optional, Dict, Any
import json as _json
import getpass

from .spec import DEFAULT_LMSTUDIO, DEFAULT_OLLAMA, DEFAULT_OPENAI
from .detect import detect_base_url, list_models
from .state import LinkerState
from .ui import err, c, BOLD, CYAN, GRAY, info, warn, ok, supports_color
from .io_safe import AUTH_JSON, atomic_write_with_backup


def _arrow_choice(prompt: str, options: List[str]) -> Optional[int]:
    """Arrow-key navigable selector. Returns index or None if unsupported."""
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        return None
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
        else:
            import termios  # type: ignore
            import tty  # type: ignore
    except Exception:
        return None

    idx = 0
    n = len(options)
    use_color = supports_color() and not os.environ.get("NO_COLOR")

    def draw():
        print()
        print(c(prompt, BOLD))
        for i, opt in enumerate(options):
            marker = "➤" if i == idx else " "
            line = f" {marker} {opt}"
            if use_color:
                if i == idx:
                    print(c(line, CYAN))
                else:
                    print(c(line, GRAY))
            else:
                print(line)

    def read_key() -> str:
        if os.name == "nt":
            import msvcrt  # type: ignore
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch == "\x1b":
                return "ESC"
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                mapping = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}
                return mapping.get(ch2, "")
            return ch
        else:
            import termios  # type: ignore
            import tty  # type: ignore
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch1 = sys.stdin.read(1)
                if ch1 in ("\r", "\n"):
                    return "ENTER"
                if ch1 != "\x1b":
                    return ch1
                ch2 = sys.stdin.read(1)
                if ch2 != "[":
                    return ""
                ch3 = sys.stdin.read(1)
                mapping = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
                return mapping.get(ch3, "")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    draw()
    while True:
        key = read_key()
        if key == "ENTER":
            print()
            return idx
        if key in ("UP", "k"):
            idx = (idx - 1) % n
        elif key in ("DOWN", "j"):
            idx = (idx + 1) % n
        elif key and key.isdigit():
            d = int(key)
            if 1 <= d <= n:
                print()
                return d - 1
        # redraw in place
        if supports_color():
            sys.stdout.write(f"\x1b[{n+1}F")
            sys.stdout.flush()
        draw()


def prompt_choice(prompt: str, options: List[str]) -> int:
    """Display a list and return the selected zero-based index.

    Uses arrow-key navigation on TTY; falls back to numeric input.
    """
    sel = _arrow_choice(prompt, options)
    if sel is not None:
        return sel
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        s = input(f"{prompt} [1-{len(options)}]: ").strip()
        if s.isdigit() and 1 <= int(s) <= len(options):
            return int(s) - 1
        err("Invalid choice.")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Simple interactive yes/no prompt. Returns True for yes, False for no.

    default controls what happens when user just hits Enter.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        s = input(f"{question} {suffix} ").strip().lower()
        if not s:
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        err("Please answer y or n.")


def _call_detect_base_url(det, state: LinkerState, auto: bool) -> str:
    try:
        sig = inspect.signature(det)
    except (TypeError, ValueError):
        sig = None

    attempts = []

    def add_attempt(args, kwargs=None) -> None:
        if kwargs is None:
            kwargs = {}
        attempts.append((args, kwargs))

    if sig is not None:
        params = list(sig.parameters.values())
        has_varargs = any(
            param.kind == inspect.Parameter.VAR_POSITIONAL for param in params
        )
        positional = [
            param
            for param in params
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        required_positional = [
            param for param in positional if param.default is inspect._empty
        ]
        if has_varargs or len(required_positional) >= 2:
            add_attempt((state, auto))
        elif len(required_positional) == 1:
            add_attempt((state,))
        else:
            add_attempt(())
    else:
        add_attempt(())

    add_attempt(())
    add_attempt((state, auto))
    add_attempt((state,))

    last_error: Optional[TypeError] = None
    for args, kwargs in attempts:
        try:
            return det(*args, **kwargs)
        except TypeError as exc:
            last_error = exc
            message = str(exc)
            if (
                "positional argument" in message
                or "positional arguments" in message
                or "required positional" in message
            ):
                continue
            raise

    if last_error is not None:
        raise last_error
    return det()


def pick_base_url(state: LinkerState, auto: bool) -> str:
    """Interactively choose or auto-detect the server base URL."""
    if auto:
        mod = sys.modules.get("codex_cli_linker")
        det = getattr(mod, "detect_base_url", detect_base_url)
        return (
            _call_detect_base_url(det, state, auto)
            or state.base_url
            or DEFAULT_LMSTUDIO
        )
    print()
    print(c("Choose base URL (OpenAI‑compatible):", BOLD))
    opts = [
        f"LM Studio default ({DEFAULT_LMSTUDIO})",
        f"Ollama default ({DEFAULT_OLLAMA})",
        f"OpenAI API ({DEFAULT_OPENAI})",
        "Custom…",
        "Auto‑detect",
        f"Use last saved ({state.base_url})",
    ]
    idx = prompt_choice("Select", opts)
    choice = opts[idx]
    if choice.startswith("LM Studio"):
        return DEFAULT_LMSTUDIO
    if choice.startswith("Ollama"):
        return DEFAULT_OLLAMA
    if choice.startswith("OpenAI API"):
        return DEFAULT_OPENAI
    if choice.startswith("Custom"):
        return input("Enter base URL (e.g., http://localhost:1234/v1): ").strip()
    if choice.startswith("Auto"):
        mod = sys.modules.get("codex_cli_linker")
        det = getattr(mod, "detect_base_url", detect_base_url)
        return (
            _call_detect_base_url(det, state, auto) or input("Enter base URL: ").strip()
        )
    return state.base_url


def pick_model_interactive(base_url: str, last: Optional[str]) -> str:
    """Prompt the user to choose a model from those available on the server."""
    info(f"Querying models from {base_url} …")
    mod = sys.modules.get("codex_cli_linker")
    lm = getattr(mod, "list_models", list_models)
    models = lm(base_url)
    print(c("Available models:", BOLD))
    labels = [m + (c("  (last)", CYAN) if m == last else "") for m in models]
    idx = prompt_choice("Pick a model", labels)
    return models[idx]


def interactive_prompts(args) -> None:
    """Collect additional configuration choices interactively."""
    print()
    print(c("CODEX CLI LINKER", BOLD))
    print()
    # APPROVAL POLICY (all allowed by spec)
    ap_opts = ["untrusted", "on-failure"]
    print()
    print(c("Approval policy:", BOLD))
    i = prompt_choice("Choose approval mode", ap_opts)
    args.approval_policy = ap_opts[i]

    # REASONING EFFORT (user-requested full set). Spec allows only minimal|low; others will be clamped.
    re_opts_full = ["minimal", "low", "medium", "high", "auto"]
    print()
    print(c("Reasoning effort:", BOLD))
    i = prompt_choice("Choose reasoning effort", re_opts_full)
    chosen_eff = re_opts_full[i]
    if chosen_eff not in ("minimal", "low"):
        warn(
            "Selected reasoning_effort is outside spec; clamping to nearest supported (low/minimal)."
        )
        chosen_eff = "low" if chosen_eff in ("medium", "high", "auto") else "minimal"
    args.reasoning_effort = chosen_eff

    # REASONING SUMMARY (all allowed by spec)
    rs_opts = ["auto", "concise"]
    print()
    print(c("Reasoning summary:", BOLD))
    i = prompt_choice("Choose reasoning summary", rs_opts)
    args.reasoning_summary = rs_opts[i]

    # VERBOSITY (all allowed by spec)
    vb_opts = ["low", "medium"]
    print()
    print(c("Model verbosity:", BOLD))
    i = prompt_choice("Choose verbosity", vb_opts)
    args.verbosity = vb_opts[i]

    # SANDBOX MODE (all allowed by spec)
    sb_opts = ["read-only", "workspace-write"]
    print()
    print(c("Sandbox mode:", BOLD))
    i = prompt_choice("Choose sandbox mode", sb_opts)
    args.sandbox_mode = sb_opts[i]

    # REASONING VISIBILITY
    print()
    print(c("Reasoning visibility:", BOLD))
    show = prompt_yes_no("Show raw agent reasoning?", default=True)
    args.show_raw_agent_reasoning = show
    args.hide_agent_reasoning = not show


def manage_profiles_interactive(args) -> None:
    """Interactive manager for profiles: list, add, edit, remove."""
    args.profile_overrides = getattr(args, "profile_overrides", {}) or {}
    while True:
        print()
        print(c("Profiles:", BOLD))
        # Build list: main current + overrides + providers_list
        names = []
        main_name = args.profile or "<auto>"
        names.append(main_name)
        for k in (args.profile_overrides or {}).keys():
            if k not in names:
                names.append(k)
        for p in (args.providers_list or []):
            if p not in names:
                names.append(p)
        for n in names:
            print(c(f" - {n}", CYAN))
        i = prompt_choice("Choose", ["Add profile", "Edit profile", "Remove profile", "Done"])
        if i == 0:
            name = input("Profile name: ").strip()
            if not name:
                continue
            provider = input("Provider id (e.g., lmstudio, ollama, openai): ").strip() or (args.provider or "")
            # start with minimal override
            args.profile_overrides[name] = {
                "provider": provider,
                "model": "",
                "model_context_window": 0,
                "model_max_output_tokens": 0,
                "approval_policy": args.approval_policy,
            }
            _edit_profile_entry_interactive(args, name)
        elif i == 1:
            if not names:
                warn("No profiles to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            target = names[idx]
            if target == main_name:
                # Edit main profile name only
                newn = input("New profile name: ").strip()
                if newn:
                    args.profile = newn
            else:
                _edit_profile_entry_interactive(args, target)
        elif i == 2:
            if not names:
                warn("No profiles to remove.")
                continue
            idx = prompt_choice("Remove which?", names)
            target = names[idx]
            if target in (args.profile_overrides or {}):
                args.profile_overrides.pop(target, None)
                info(f"Removed override: {target}")
            elif target in (args.providers_list or []):
                args.providers_list = [p for p in args.providers_list if p != target]
                info(f"Removed provider profile: {target}")
            elif target == main_name:
                warn("Won't remove the current active profile; rename instead.")
        else:
            break


def _edit_profile_entry_interactive(args, name: str) -> None:
    ov = dict((getattr(args, "profile_overrides", {}) or {}).get(name) or {})
    if not ov:
        ov = {"provider": args.provider or "", "model": "", "model_context_window": 0, "model_max_output_tokens": 0, "approval_policy": args.approval_policy}
    while True:
        print()
        print(c(f"Edit profile [{name}]", BOLD))
        items = [
            ("Provider", ov.get("provider") or ""),
            ("Model", ov.get("model") or ""),
            ("Context window", str(ov.get("model_context_window") or 0)),
            ("Max output tokens", str(ov.get("model_max_output_tokens") or 0)),
            ("Approval policy", ov.get("approval_policy") or args.approval_policy),
        ]
        for i, (lbl, val) in enumerate(items, 1):
            print(f"  {i}. {lbl}: {val}")
        act = prompt_choice("Action", ["Edit field", "Save", "Cancel"])
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                ov["provider"] = input("Provider: ").strip() or ov.get("provider") or ""
            elif idx == 1:
                ov["model"] = input("Model: ").strip() or ov.get("model") or ""
            elif idx == 2:
                try:
                    ov["model_context_window"] = int(input("Context window: ").strip() or "0")
                except Exception:
                    pass
            elif idx == 3:
                try:
                    ov["model_max_output_tokens"] = int(input("Max output tokens: ").strip() or "0")
                except Exception:
                    pass
            elif idx == 4:
                i2 = prompt_choice("Approval policy", ["untrusted", "on-failure", "on-request", "never"])
                ov["approval_policy"] = ["untrusted", "on-failure", "on-request", "never"][i2]
        elif act == 1:
            args.profile_overrides[name] = ov
            ok("Saved.")
            return
        else:
            return


def interactive_settings_editor(state: LinkerState, args) -> str:
    """Unified list-based editor for common settings with a management hub.

    Returns one of: "write", "overwrite", "write_and_launch", "quit".
    Mutates args/state in-place based on user selections.
    """
    while True:
        print()
        print(c("Interactive settings:", BOLD))
        hub = prompt_choice(
            "Start with",
            ["Manage profiles", "Manage MCP servers", "Edit run settings", "Proceed"],
        )
        if hub == 0:
            manage_profiles_interactive(args)
            continue
        if hub == 1:
            manage_mcp_servers_interactive(args)
            continue
        if hub == 3:
            # proceed to write
            return "write"
        items = [
            ("Profile name", args.profile or state.profile or state.provider or "<auto>"),
            ("Provider", args.provider or state.provider or "<auto>"),
            ("Base URL", state.base_url or args.base_url or "<auto>"),
            ("Model", args.model or state.model or "<pick>"),
            ("Auth (OpenAI)", getattr(args, "preferred_auth_method", "apikey")),
        ]
        # API key status (OpenAI only)
        if (args.provider or state.provider) == "openai":
            existing_key = ""
            if AUTH_JSON.exists():
                try:
                    data = _json.loads(AUTH_JSON.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        existing_key = str(data.get("OPENAI_API_KEY") or "")
                except Exception:
                    existing_key = ""
            status = "set" if existing_key else "missing"
            items.append(("API key (OPENAI_API_KEY)", status))
        # Rest of settings
        items.extend([
            ("Approval policy", args.approval_policy),
            ("Sandbox mode", args.sandbox_mode),
            ("Network access", "true" if getattr(args, "network_access", None) else "false"),
            (
                "Exclude $TMPDIR",
                "true" if getattr(args, "exclude_tmpdir_env_var", None) else "false",
            ),
            ("Exclude /tmp", "true" if getattr(args, "exclude_slash_tmp", None) else "false"),
            ("Writable roots (CSV)", getattr(args, "writable_roots", "") or ""),
            ("File opener", args.file_opener),
            ("Context window", str(args.model_context_window or 0)),
            ("Max output tokens", str(args.model_max_output_tokens or 0)),
            ("Reasoning effort", args.reasoning_effort),
            ("Reasoning summary", args.reasoning_summary),
            ("Verbosity", args.verbosity),
            ("Disable response storage", "true" if args.disable_response_storage else "false"),
            ("History persistence", "none" if args.no_history else "save-all"),
            ("History max bytes", str(args.history_max_bytes or 0)),
            ("Tools: web_search", "true" if args.tools_web_search else "false"),
            ("Wire API", getattr(args, "wire_api", "chat")),
            ("ChatGPT base URL", args.chatgpt_base_url or ""),
            ("Azure api-version", args.azure_api_version or ""),
            ("HTTP headers (CSV KEY=VAL)", ",".join(getattr(args, "http_header", []) or []) or ""),
            ("Env HTTP headers (CSV KEY=ENV)", ",".join(getattr(args, "env_http_header", []) or []) or ""),
            ("Notify (CSV or JSON array)", getattr(args, "notify", "") or ""),
            ("Instructions", args.instructions or ""),
            ("Trusted projects (CSV)", ",".join(getattr(args, "trust_project", []) or []) or ""),
            ("Env key name", getattr(args, "env_key_name", "NULLKEY")),
            ("TUI notifications", "custom" if getattr(args, "tui_notification_types", "") else ("true" if getattr(args, "tui_notifications", None) else "false")),
            ("TUI notification types (CSV)", getattr(args, "tui_notification_types", "") or ""),
            ("Manage profiles…", "open"),
            ("Manage MCP servers…", "open"),
        ])
        for i, (label, val) in enumerate(items, 1):
            # Dim unchanged metadata for readability
            show = f"  {i}. {label}: {val}"
            print(c(show, GRAY) if "Manage" not in label and label not in ("Profile name","Provider","Base URL","Model") else show)
        print()
        action_idx = prompt_choice(
            "Select item to edit or action",
            [
                "Edit item (enter number)",
                "Write",
                "Overwrite + Write",
                "Write and launch (print cmd)",
                "Quit (no write)",
            ],
        )
        if action_idx == 0:
            s = input("Item number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx < 0 or idx >= len(items):
                continue
            label = items[idx][0]
            if label == "Profile name":
                newp = input("Profile name: ").strip()
                if newp:
                    args.profile = newp
            elif label == "Provider":
                newprov = input("Provider id (e.g., lmstudio, ollama, openai, custom): ").strip()
                if newprov:
                    args.provider = newprov
                    state.provider = newprov
            elif label == "Base URL":
                # Reuse base URL picker
                state.base_url = pick_base_url(state, False)
            elif label == "Model":
                # Model picker requires a base_url; prompt if missing
                if not state.base_url:
                    state.base_url = pick_base_url(state, False)
                try:
                    state.model = pick_model_interactive(state.base_url, state.model or None)
                except Exception as e:
                    err(str(e))
            elif label == "Auth (OpenAI)":
                i2 = prompt_choice("OpenAI auth method", ["apikey", "chatgpt"])
                args.preferred_auth_method = "apikey" if i2 == 0 else "chatgpt"
            elif label == "API key (OPENAI_API_KEY)":
                # Set or update OPENAI_API_KEY in auth.json
                try:
                    new_key = getpass.getpass("Enter OPENAI_API_KEY (input hidden): ").strip()
                except Exception as exc:  # pragma: no cover
                    err(f"Could not read input: {exc}")
                    new_key = ""
                if new_key:
                    current = {}
                    if AUTH_JSON.exists():
                        try:
                            current = _json.loads(AUTH_JSON.read_text(encoding="utf-8"))
                            if not isinstance(current, dict):
                                current = {}
                        except Exception:
                            current = {}
                    current["OPENAI_API_KEY"] = new_key
                    atomic_write_with_backup(AUTH_JSON, _json.dumps(current, indent=2) + "\n")
                    ok(f"Updated {AUTH_JSON} with OPENAI_API_KEY")
                    warn("Never commit this file; it contains a secret.")
            elif label == "Approval policy":
                i2 = prompt_choice("Choose", ["untrusted", "on-failure"])
                args.approval_policy = "untrusted" if i2 == 0 else "on-failure"
            elif label == "Sandbox mode":
                i2 = prompt_choice(
                    "Choose", ["read-only", "workspace-write", "danger-full-access"]
                )
                args.sandbox_mode = [
                    "read-only",
                    "workspace-write",
                    "danger-full-access",
                ][i2]
            elif label == "Network access":
                i2 = prompt_choice("Network access", ["true", "false"])
                args.network_access = True if i2 == 0 else False
            elif label == "Exclude $TMPDIR":
                i2 = prompt_choice("Exclude $TMPDIR", ["true", "false"])
                args.exclude_tmpdir_env_var = True if i2 == 0 else False
            elif label == "Exclude /tmp":
                i2 = prompt_choice("Exclude /tmp", ["true", "false"])
                args.exclude_slash_tmp = True if i2 == 0 else False
            elif label == "Writable roots (CSV)":
                args.writable_roots = input("Writable roots CSV: ").strip()
            elif label == "File opener":
                i2 = prompt_choice("File opener", ["vscode", "vscode-insiders", "windsurf", "cursor", "none"])
                args.file_opener = ["vscode", "vscode-insiders", "windsurf", "cursor", "none"][i2]
            elif label == "Context window":
                try:
                    args.model_context_window = int(input("Context window: ").strip() or "0")
                except Exception:
                    pass
            elif label == "Max output tokens":
                try:
                    args.model_max_output_tokens = int(input("Max output tokens: ").strip() or "0")
                except Exception:
                    pass
            elif label == "Reasoning effort":
                i2 = prompt_choice("Effort", ["minimal", "low", "medium", "high"])
                args.reasoning_effort = ["minimal", "low", "medium", "high"][i2]
            elif label == "Reasoning summary":
                i2 = prompt_choice("Summary", ["auto", "concise", "detailed", "none"])
                args.reasoning_summary = ["auto", "concise", "detailed", "none"][i2]
            elif label == "Verbosity":
                i2 = prompt_choice("Verbosity", ["low", "medium", "high"])
                args.verbosity = ["low", "medium", "high"][i2]
            elif label == "Disable response storage":
                i2 = prompt_choice("Disable response storage", ["true", "false"])
                args.disable_response_storage = True if i2 == 0 else False
            elif label == "History persistence":
                i2 = prompt_choice("History persistence", ["save-all", "none"])
                args.no_history = True if i2 == 1 else False
            elif label == "History max bytes":
                try:
                    args.history_max_bytes = int(input("History max bytes: ").strip() or "0")
                except Exception:
                    pass
            elif label == "Tools: web_search":
                i2 = prompt_choice("tools.web_search", ["true", "false"])
                args.tools_web_search = True if i2 == 0 else False
            elif label == "Wire API":
                i2 = prompt_choice("Wire API", ["chat", "responses"])
                args.wire_api = ["chat", "responses"][i2]
            elif label == "ChatGPT base URL":
                args.chatgpt_base_url = input("ChatGPT base URL: ").strip()
            elif label == "Azure api-version":
                args.azure_api_version = input("Azure api-version: ").strip()
            elif label == "HTTP headers (CSV KEY=VAL)":
                raw = input("Headers CSV: ").strip()
                args.http_header = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Env HTTP headers (CSV KEY=ENV)":
                raw = input("Env headers CSV: ").strip()
                args.env_http_header = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Notify (CSV or JSON array)":
                args.notify = input("Notify (CSV or JSON array): ").strip()
            elif label == "Instructions":
                args.instructions = input("Instructions: ").strip()
            elif label == "Trusted projects (CSV)":
                raw = input("Trusted projects CSV: ").strip()
                args.trust_project = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Env key name":
                args.env_key_name = input("Env key name: ").strip() or args.env_key_name
            elif label == "TUI notifications":
                i2 = prompt_choice("TUI notifications", ["disabled", "enabled (all)", "filter types"])
                if i2 == 0:
                    args.tui_notifications = False
                    args.tui_notification_types = ""
                elif i2 == 1:
                    args.tui_notifications = True
                    args.tui_notification_types = ""
                else:
                    args.tui_notifications = None
                    args.tui_notification_types = input("Types CSV (agent-turn-complete,approval-requested): ").strip()
            elif label == "TUI notification types (CSV)":
                args.tui_notification_types = input("Types CSV (agent-turn-complete,approval-requested): ").strip()
            elif label == "Manage profiles…":
                manage_profiles_interactive(args)
            elif label == "Manage MCP servers…":
                manage_mcp_servers_interactive(args)
            continue
        elif action_idx == 1:
            return "write"
        elif action_idx == 2:
            return "overwrite"
        elif action_idx == 3:
            return "write_and_launch"
        else:
            return "quit"


def _input_list_csv(prompt: str, default: Optional[List[str]] = None) -> List[str]:
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _input_env_kv(prompt: str, default: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return dict(default)
    env: Dict[str, str] = {}
    if not raw:
        return env
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                env[k] = v
    return env


def manage_mcp_servers_interactive(args) -> None:
    """Interactive editor for args.mcp_servers, written under top-level key mcp_servers.

    Each server entry supports keys: command (str), args (list[str]), env (map),
    and optional startup_timeout_ms (int, default 10000).
    """
    def list_servers() -> List[str]:
        return sorted(list((args.mcp_servers or {}).keys()))

    while True:
        names = list_servers()
        print()
        print(c("MCP servers:", BOLD))
        if not names:
            info("(none)")
        else:
            for n in names:
                curr = dict((args.mcp_servers or {}).get(n) or {})
                cmd = curr.get("command", "npx")
                a = curr.get("args") or ["-y", "mcp-server"]
                env = curr.get("env") or {}
                to_ms = curr.get("startup_timeout_ms", 10000)
                print(c(f" - {n}", CYAN))
                print(c(f"    command: {cmd}", GRAY))
                print(c(f"    args: {', '.join(a)}", GRAY))
                if env:
                    kv = ", ".join(f"{k}={v}" for k, v in env.items())
                    print(c(f"    env: {kv}", GRAY))
                print(c(f"    startup_timeout_ms: {to_ms}", GRAY))
        i = prompt_choice("Choose", ["Add server", "Edit server", "Remove server", "Done"])
        if i == 0:
            name = input("Server name (identifier): ").strip()
            if not name:
                continue
            entry: Dict[str, Any] = {"command": "npx", "args": ["-y", "mcp-server"], "env": {}}
            _edit_mcp_entry_interactive(args, name, entry, creating=True)
        elif i == 1:
            if not names:
                warn("No servers to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            name = names[idx]
            curr = dict((args.mcp_servers or {}).get(name) or {})
            _edit_mcp_entry_interactive(args, name, curr or {"command": "npx", "args": ["-y", "mcp-server"], "env": {}}, creating=False)
        elif i == 2:
            if not names:
                warn("No servers to remove.")
                continue
            idx = prompt_choice("Remove which?", names)
            name = names[idx]
            m = dict(args.mcp_servers or {})
            m.pop(name, None)
            args.mcp_servers = m
            info(f"Removed mcp server '{name}'")
        else:
            break


def _edit_mcp_entry_interactive(args, name: str, entry: Dict[str, Any], creating: bool) -> None:
    curr = dict(entry)
    while True:
        print()
        print(c(f"Edit MCP server [{name}]", BOLD))
        items = [
            ("Command", curr.get("command", "npx")),
            ("Args (CSV)", ", ".join(curr.get("args") or [])),
            ("Env (CSV KEY=VAL)", ", ".join(f"{k}={v}" for k, v in (curr.get("env") or {}).items())),
            ("Startup timeout (ms)", str(curr.get("startup_timeout_ms", 10000))),
        ]
        for i, (lbl, val) in enumerate(items, 1):
            print(f"  {i}. {lbl}: {val}")
        act = prompt_choice("Action", ["Edit field", "Save", "Cancel"])
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                curr["command"] = input("Command: ").strip() or curr.get("command", "npx")
            elif idx == 1:
                curr["args"] = _input_list_csv("Args CSV: ", curr.get("args") or ["-y", "mcp-server"])
            elif idx == 2:
                curr["env"] = _input_env_kv("Env CSV (KEY=VAL,...): ", curr.get("env") or {})
            elif idx == 3:
                try:
                    curr["startup_timeout_ms"] = int(input("Startup timeout (ms): ").strip() or "10000")
                except Exception:
                    pass
        elif act == 1:
            args.mcp_servers = dict(args.mcp_servers or {})
            args.mcp_servers[name] = curr
            if creating:
                ok(f"Added mcp server '{name}'")
            else:
                ok(f"Updated mcp server '{name}'")
            return
        else:
            return


__all__ = [
    "prompt_choice",
    "prompt_yes_no",
    "pick_base_url",
    "pick_model_interactive",
    "interactive_prompts",
    "interactive_settings_editor",
    "manage_profiles_interactive",
    "manage_mcp_servers_interactive",
]
