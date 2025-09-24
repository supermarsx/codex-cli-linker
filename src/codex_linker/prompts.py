from __future__ import annotations

import inspect
import sys
import os
from typing import List, Optional, Dict, Any
import json as _json
import getpass

from .spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_OPENAI,
    DEFAULT_OPENROUTER,
    DEFAULT_OPENROUTER_LOCAL,
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
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    PROVIDER_LABELS,
)
from .detect import detect_base_url, list_models
from .detect import try_auto_context_window  # type: ignore
from .state import LinkerState
from .ui import (
    err,
    c,
    BOLD,
    CYAN,
    GRAY,
    info,
    warn,
    ok,
    supports_color,
    RED,
    YELLOW,
    GREEN,
    BLUE,
    MAGENTA,
)
from .io_safe import AUTH_JSON, atomic_write_with_backup, write_auth_json_merge

# Track Ctrl-C presses at the hub to support "double Ctrl-C to exit"
_HUB_CTRL_C_COUNT = 0


def _handle_ctrlc_in_hub() -> None:
    """On first Ctrl-C at the hub, warn; on second, exit.

    This avoids accidentally quitting the tool. Editors and nested flows should
    catch KeyboardInterrupt and return to the hub.
    """
    global _HUB_CTRL_C_COUNT
    _HUB_CTRL_C_COUNT += 1
    if _HUB_CTRL_C_COUNT >= 2:
        print()
        sys.exit(0)
    warn("Press Ctrl-C again to exit. Returning to main menu…")


def _safe_input(prompt: str) -> str:
    """input() that propagates Ctrl-C so callers can decide behavior."""
    try:
        return input(prompt)
    except KeyboardInterrupt:
        print()
        raise


def _is_null_input(s: str) -> bool:
    try:
        return s.strip().lower() == "null"
    except Exception:
        return False


def _arrow_choice(prompt: str, options: List[str]) -> Optional[int]:
    """Arrow-key navigable selector. Returns index or None if unsupported."""
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        return None
    try:
        if os.name == "nt":
            import msvcrt as _ms  # type: ignore

            del _ms
        else:
            import termios as _t  # type: ignore
            import tty as _ty  # type: ignore

            del _t, _ty
    except Exception:
        return None

    idx = 0
    n = len(options)
    use_color = supports_color() and not os.environ.get("NO_COLOR")
    numbuf: str = ""

    def draw():
        # Render header and options without inserting an extra blank line each redraw
        print(c(prompt, BOLD))
        palette = [RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA]
        for i, opt in enumerate(options):
            marker = "➤" if i == idx else " "
            line = f" {marker} {opt}"
            if use_color:
                col = palette[i % len(palette)] if palette else CYAN
                if i == idx:
                    print(c(line, col + BOLD))
                else:
                    print(c(line, col))
            else:
                print(line)

    def read_key() -> str:
        if os.name == "nt":
            import msvcrt  # type: ignore

            ch = msvcrt.getwch()
            if ch == "\x03":  # Ctrl-C
                return "CTRL_C"
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch == "\x1b":
                return "ESC"
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                mapping = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}
                return mapping.get(ch2, "")
            if ch == "\x08":
                return "BACKSPACE"
            return ch
        else:
            import termios  # type: ignore
            import tty  # type: ignore

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch1 = sys.stdin.read(1)
                if ch1 == "\x03":  # Ctrl-C
                    return "CTRL_C"
                if ch1 in ("\r", "\n"):
                    return "ENTER"
                if ch1 == "\x7f":
                    return "BACKSPACE"
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

    # Initial render
    draw()
    while True:
        key = read_key()
        if key == "CTRL_C":
            print()
            raise KeyboardInterrupt
        if key == "ENTER":
            # If user typed numeric input, use it
            if numbuf and numbuf.isdigit():
                sel = int(numbuf)
                if 1 <= sel <= n:
                    print()
                    return sel - 1
            print()
            return idx
        if key in ("UP", "k"):
            idx = (idx - 1) % n
            numbuf = ""
        elif key in ("DOWN", "j"):
            idx = (idx + 1) % n
            numbuf = ""
        elif key == "BACKSPACE":
            numbuf = numbuf[:-1]
            if numbuf.isdigit() and 1 <= int(numbuf) <= n:
                idx = int(numbuf) - 1
        elif key and key.isdigit():
            # Accumulate multi-digit numeric selection and preview
            numbuf += key
            if numbuf.isdigit() and 1 <= int(numbuf) <= n:
                idx = int(numbuf) - 1
        # redraw in place: move cursor to the start of the block and repaint
        if supports_color():
            sys.stdout.write(f"\x1b[{n+1}F")  # up header+options lines
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
        use_color = supports_color() and not os.environ.get("NO_COLOR")
        if use_color:
            palette = [RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA]
            col = palette[(i - 1) % len(palette)]
            print(c(f"  {i}. {opt}", col))
        else:
            print(f"  {i}. {opt}")
    while True:
        s = _safe_input(f"{prompt} [1-{len(options)}]: ").strip()
        if s.isdigit() and 1 <= int(s) <= len(options):
            return int(s) - 1
        err("Invalid choice.")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Simple interactive yes/no prompt. Returns True for yes, False for no.

    default controls what happens when user just hits Enter.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        s = _safe_input(f"{question} {suffix} ").strip().lower()
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
        "Custom…",
        "Auto‑detect",
        f"Use last saved ({state.base_url})",
        f"OpenAI API ({DEFAULT_OPENAI})",
        f"OpenRouter ({DEFAULT_OPENROUTER})",
        f"Anthropic ({DEFAULT_ANTHROPIC})",
        f"Groq ({DEFAULT_GROQ})",
        f"Mistral ({DEFAULT_MISTRAL})",
        f"DeepSeek ({DEFAULT_DEEPSEEK})",
        f"Cohere ({DEFAULT_COHERE})",
        f"Baseten ({DEFAULT_BASETEN})",
        f"KoboldCpp ({DEFAULT_KOBOLDCPP})",
        "Azure OpenAI (enter resource + path)",
    ]
    idx = prompt_choice("Select", opts)
    choice = opts[idx]
    if choice.startswith("LM Studio"):
        return DEFAULT_LMSTUDIO
    if choice.startswith("Ollama"):
        return DEFAULT_OLLAMA
    if choice.startswith("OpenAI API"):
        return DEFAULT_OPENAI
    if choice.startswith("OpenRouter"):
        return DEFAULT_OPENROUTER
    if choice.startswith("Anthropic"):
        return DEFAULT_ANTHROPIC
    if choice.startswith("Groq"):
        return DEFAULT_GROQ
    if choice.startswith("Mistral"):
        return DEFAULT_MISTRAL
    if choice.startswith("DeepSeek"):
        return DEFAULT_DEEPSEEK
    if choice.startswith("Cohere"):
        return DEFAULT_COHERE
    if choice.startswith("Baseten"):
        return DEFAULT_BASETEN
    if choice.startswith("KoboldCpp"):
        return DEFAULT_KOBOLDCPP
    if choice.startswith("AnythingLLM"):
        return DEFAULT_ANYTHINGLLM
    if choice.startswith("Jan AI"):
        return DEFAULT_JAN
    if choice.startswith("llama.cpp"):
        return DEFAULT_LLAMACPP
    if choice.startswith("Azure OpenAI"):
        resource = _safe_input("Azure resource name (e.g., myres): ").strip()
        path = _safe_input("Path (e.g., openai): ").strip()
        if not resource:
            resource = "<resource>"
        if not path:
            path = "openai"
        return f"https://{resource}.openai.azure.com/{path}"
    if choice.startswith("Custom"):
        return _safe_input("Enter base URL (e.g., http://localhost:1234/v1): ").strip()
    if choice.startswith("Auto"):
        mod = sys.modules.get("codex_cli_linker")
        det = getattr(mod, "detect_base_url", detect_base_url)
        return (
            _call_detect_base_url(det, state, auto) or _safe_input("Enter base URL: ").strip()
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
        # Build list: main current + profile overrides (providers are managed separately)
        names = []
        main_name = args.profile or "<auto>"
        names.append(main_name)
        for k in (args.profile_overrides or {}).keys():
            if k not in names:
                names.append(k)
        for n in names:
            print(c(f" - {n}", CYAN))
        i = prompt_choice(
            "Choose", ["Add profile", "Edit profile", "Remove profile", "Go back"]
        )
        if i == 0:
            name = _safe_input("Profile name: ").strip()
            if not name:
                continue
            # Choose provider via existing, presets, or manual (or go back to main)
            src = prompt_choice(
                "Provider source",
                [
                    "Choose from existing providers",
                    "Pick from presets",
                    "Enter id manually",
                    "Go back to main menu",
                ],
            )
            if src == 3:
                # Return all the way to the main interactive hub
                return
            if src == 0:
                # From existing configured providers
                names = []
                if getattr(args, "provider", None):
                    names.append(args.provider)
                for k in (getattr(args, "provider_overrides", {}) or {}).keys():
                    if k not in names:
                        names.append(k)
                for p in (getattr(args, "providers_list", []) or []):
                    if p not in names:
                        names.append(p)
                if not names:
                    warn("No providers configured yet; use presets or manual entry.")
                    continue
                pi = prompt_choice("Use which provider?", names)
                provider = names[pi]
            elif src == 1:
                # Build preset list from PROVIDER_LABELS and add OpenAI auth variants
                base_presets = sorted(
                    [(pid, lbl) for pid, lbl in PROVIDER_LABELS.items()],
                    key=lambda x: x[1].lower(),
                )
                # Insert distinct OpenAI auth-mode presets
                extended_presets = [("openai:api", "OpenAI (API Key)"), ("openai:chatgpt", "OpenAI (ChatGPT)")]
                presets = extended_presets + base_presets
                labels = [
                    (f"{lbl} ({pid.split(':')[0]})" if ":" in pid else f"{lbl} ({pid})")
                    for pid, lbl in presets
                ]
                labels.append("Go back to main menu")
                sel = prompt_choice("Choose preset", labels)
                if sel == len(labels) - 1:
                    return
                chosen = presets[sel][0]
                # Map selection to provider + auth mode
                if chosen == "openai:api":
                    provider = "openai"
                    # Set preferred_auth_method and env key for OpenAI API preset
                    args.preferred_auth_method = "apikey"
                    if not getattr(args, "env_key_name", "") or getattr(args, "env_key_name", "") in ("", "NULLKEY"):
                        args.env_key_name = "OPENAI_API_KEY"
                    if not ((getattr(args, "base_url", "") or "").strip()):
                        args.base_url = DEFAULT_OPENAI
                elif chosen == "openai:chatgpt":
                    provider = "openai"
                    args.preferred_auth_method = "chatgpt"
                    if not ((getattr(args, "base_url", "") or "").strip()):
                        args.base_url = DEFAULT_OPENAI
                else:
                    provider = chosen
                # Auto-fill basics: base_url and env key name when possible
                try:
                    # Base URL defaults per provider
                    default_base_by_provider = {
                        "lmstudio": DEFAULT_LMSTUDIO,
                        "ollama": DEFAULT_OLLAMA,
                        "openai": DEFAULT_OPENAI,
                        "openrouter-remote": DEFAULT_OPENROUTER,
                        "anthropic": DEFAULT_ANTHROPIC,
                        "groq": DEFAULT_GROQ,
                        "mistral": DEFAULT_MISTRAL,
                        "deepseek": DEFAULT_DEEPSEEK,
                        "cohere": DEFAULT_COHERE,
                        "baseten": DEFAULT_BASETEN,
                        "llamacpp": DEFAULT_LLAMACPP,
                        "koboldcpp": DEFAULT_KOBOLDCPP,
                        "jan": DEFAULT_JAN,
                        "anythingllm": DEFAULT_ANYTHINGLLM,
                    }
                    if not ((getattr(args, "base_url", "") or "").strip()):
                        if provider != "azure":  # Azure requires resource name
                            args.base_url = default_base_by_provider.get(provider, getattr(args, "base_url", ""))
                    # Env var defaults per provider
                    default_envs = {
                        "openai": "OPENAI_API_KEY",
                        "openrouter-remote": "OPENROUTER_API_KEY",
                        "anthropic": "ANTHROPIC_API_KEY",
                        "azure": "AZURE_OPENAI_API_KEY",
                        "groq": "GROQ_API_KEY",
                        "mistral": "MISTRAL_API_KEY",
                        "deepseek": "DEEPSEEK_API_KEY",
                        "cohere": "COHERE_API_KEY",
                        "baseten": "BASETEN_API_KEY",
                    }
                    current_env_key = getattr(args, "env_key_name", "NULLKEY") or "NULLKEY"
                    if current_env_key in ("", "NULLKEY") and provider in default_envs and getattr(args, "preferred_auth_method", "apikey") == "apikey":
                        args.env_key_name = default_envs[provider]
                except Exception:
                    pass
            else:
                provider = _safe_input(
                    "Provider id (e.g., lmstudio, ollama, openai): "
                ).strip() or (args.provider or "")
            # start with minimal override
            # For third-party online providers, prompt for API key and env name
            try:
                online = {"openai","openrouter-remote","anthropic","azure","groq","mistral","deepseek","cohere","baseten"}
                if (provider in online) and (getattr(args, "preferred_auth_method", "apikey") == "apikey"):
                    current = getattr(args, "env_key_name", "NULLKEY") or "NULLKEY"
                    if current in ("", "NULLKEY"):
                        args.env_key_name = _default_env_key_for_profile(provider, name)
                    try:
                        secret = getpass.getpass(f"Enter API key for {provider} (env {args.env_key_name}) [leave blank to skip]: ").strip()
                    except Exception:
                        secret = input(f"Enter API key for {provider} (env {args.env_key_name}) [leave blank to skip]: ").strip()
                    if secret:
                        import json as _json
                        try:
                            write_auth_json_merge(AUTH_JSON, {args.env_key_name: secret})
                            ok(f"Updated {AUTH_JSON} with {args.env_key_name}")
                            warn("Never commit this file; it contains a secret.")
                        except Exception as e:
                            err(f"Could not update {AUTH_JSON}: {e}")
            except Exception:
                pass
            args.profile_overrides[name] = {
                "provider": provider,
                "model": "",
                "model_context_window": 0,
                "model_max_output_tokens": 0,
                "approval_policy": args.approval_policy,
            }
            # Offer to show fields or jump into editor
            while True:
                step = prompt_choice(
                    "Next",
                    [
                        "Start editing",
                        "Show all fields",
                        "Save",
                    ],
                )
                if step == 0:
                    _edit_profile_entry_interactive(args, name)
                    break
                elif step == 1:
                    ov = args.profile_overrides.get(name, {})
                    print()
                    print(c(f"Profile fields [{name}]", BOLD))
                    print(f"  Provider: {ov.get('provider','')}")
                    print(f"  Model: {ov.get('model','')}")
                    print(
                        f"  Context window: {int(ov.get('model_context_window') or 0)}"
                    )
                    print(
                        f"  Max output tokens: {int(ov.get('model_max_output_tokens') or 0)}"
                    )
                    print(f"  Approval policy: {ov.get('approval_policy','')}")
                    print(f"  File opener: {ov.get('file_opener','')}")
                    print(f"  Reasoning effort: {ov.get('model_reasoning_effort','')}")
                    print(f"  Reasoning summary: {ov.get('model_reasoning_summary','')}")
                    print(f"  Verbosity: {ov.get('model_verbosity','')}")
                    print(
                        f"  Disable response storage: {str(ov.get('disable_response_storage', False)).lower()}"
                    )
                    print(f"  Sandbox mode: {ov.get('sandbox_mode','')}")
                    print(f"  ChatGPT base URL: {ov.get('chatgpt_base_url','')}")
                    print(f"  Preferred auth method: {ov.get('preferred_auth_method','')}")
                    # loop back to offer editing/saving
                else:
                    ok("Saved.")
                    break
        elif i == 1:
            if not names:
                warn("No profiles to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            target = names[idx]
            if target == main_name:
                # Edit main profile name only
                newn = _safe_input("New profile name: ").strip()
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
            if target == main_name:
                warn("Won't remove the current active profile; rename instead.")
            else:
                if prompt_yes_no(f"Remove profile '{target}'?", default=False):
                    if target in (args.profile_overrides or {}):
                        args.profile_overrides.pop(target, None)
                        info(f"Removed override: {target}")
                    elif target in (args.providers_list or []):
                        args.providers_list = [p for p in args.providers_list if p != target]
                        info(f"Removed provider profile: {target}")
                else:
                    info("Removal cancelled.")
        else:
            break


def _edit_profile_entry_interactive(args, name: str) -> None:
    ov = dict((getattr(args, "profile_overrides", {}) or {}).get(name) or {})
    if not ov:
        ov = {
            "provider": args.provider or "",
            "model": "",
            "model_context_window": 0,
            "model_max_output_tokens": 0,
            "approval_policy": args.approval_policy,
        }
    while True:
        print()
        print(c(f"Edit profile [{name}]", BOLD))
        # Build defaults reference for descriptions
        df_approval = args.approval_policy
        df_sandbox = args.sandbox_mode
        df_file_opener = args.file_opener
        df_reason_effort = getattr(args, "reasoning_effort", "")
        df_reason_summary = getattr(args, "reasoning_summary", "")
        df_verbosity = getattr(args, "verbosity", "")
        df_disable_resp = False
        df_chatgpt_base = getattr(args, "chatgpt_base_url", "") or ""
        df_auth_method = getattr(args, "preferred_auth_method", "") or ""
        df_hide = bool(getattr(args, "hide_agent_reasoning", False))
        df_show_raw = bool(getattr(args, "show_raw_agent_reasoning", False))
        df_supports_summ = bool(getattr(args, "model_supports_reasoning_summaries", False))
        df_hist_p = "none" if getattr(args, "no_history", False) else "save-all"
        df_hist_b = getattr(args, "history_max_bytes", 0) or 0
        df_tools_ws = bool(getattr(args, "tools_web_search", False))
        items = [
            ("Provider", ov.get("provider") or "", f"Default: {args.provider or ''}"),
            ("Model", ov.get("model") or "", f"Default: {getattr(args, 'model', '') or 'gpt-5'}"),
            ("Context window", str(ov.get("model_context_window") or 0), "Default: 0"),
            ("Max output tokens", str(ov.get("model_max_output_tokens") or 0), "Default: 0"),
            ("Approval policy", ov.get("approval_policy") or df_approval, f"Default: {df_approval}"),
            ("File opener", ov.get("file_opener") or "", f"Default: {df_file_opener}"),
            ("Reasoning effort", ov.get("model_reasoning_effort") or "", f"Default: {df_reason_effort or 'minimal/low'}"),
            ("Reasoning summary", ov.get("model_reasoning_summary") or "", f"Default: {df_reason_summary or 'auto'}"),
            ("Verbosity", ov.get("model_verbosity") or "", f"Default: {df_verbosity or 'medium'}"),
            ("Disable response storage", "true" if ov.get("disable_response_storage") else "false", f"Default: {'true' if df_disable_resp else 'false'}"),
            ("Sandbox mode", ov.get("sandbox_mode") or "", f"Default: {df_sandbox}"),
            ("ChatGPT base URL", ov.get("chatgpt_base_url") or "", f"Default: {df_chatgpt_base or '<empty>'}"),
            ("Preferred auth method", ov.get("preferred_auth_method") or "", f"Default: {df_auth_method or 'apikey'}"),
            ("Hide agent reasoning", "true" if ov.get("hide_agent_reasoning") else "false", f"Default: {'true' if df_hide else 'false'}"),
            ("Show raw agent reasoning", "true" if ov.get("show_raw_agent_reasoning") else "false", f"Default: {'true' if df_show_raw else 'false'}"),
            ("Model supports reasoning summaries", "true" if ov.get("model_supports_reasoning_summaries") else "false", f"Default: {'true' if df_supports_summ else 'false'}"),
            ("History persistence", (ov.get("history_persistence") or df_hist_p), f"Default: {df_hist_p}"),
            ("History max bytes", str(ov.get("history_max_bytes") if ov.get("history_max_bytes") is not None else df_hist_b), f"Default: {df_hist_b}"),
            ("Tools: web_search", "true" if ov.get("tools_web_search") else "false", f"Default: {'true' if df_tools_ws else 'false'}"),
        ]
        for i, (lbl, val, dsc) in enumerate(items, 1):
            line = f"  {i}. {lbl}: {val}"
            if dsc:
                line += " " + c(f"[{dsc}]", GRAY)
            print(line)
        act = prompt_choice(
            "Action",
            [
                "Edit field",
                "Edit all fields",
                "Save",
                "Cancel",
                "Go back to main menu",
            ],
        )
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                # Choose provider from existing or enter manually
                m = prompt_choice(
                    "Set provider",
                    ["Choose from existing providers", "Enter manually"],
                )
                if m == 0:
                    names = []
                    if getattr(args, "provider", None):
                        names.append(args.provider)
                    for k in (getattr(args, "provider_overrides", {}) or {}).keys():
                        if k not in names:
                            names.append(k)
                    for p in (getattr(args, "providers_list", []) or []):
                        if p not in names:
                            names.append(p)
                    if not names:
                        warn("No providers configured; enter manually.")
                        ov["provider"] = _safe_input("Provider: ").strip() or ov.get("provider") or ""
                    else:
                        pi = prompt_choice("Use which provider?", names)
                        ov["provider"] = names[pi]
                else:
                    ov["provider"] = _safe_input("Provider: ").strip() or ov.get("provider") or ""
            elif idx == 1:
                # Model: allow manual entry or auto-detect from server
                mode = prompt_choice("Set model", ["Enter manually", "Auto-detect from server"])
                if mode == 0:
                    ov["model"] = _safe_input("Model: ").strip() or ov.get("model") or ""
                else:
                    base = (getattr(args, "base_url", "") or "").strip()
                    if not base:
                        base = _safe_input("Base URL for model list (e.g., http://localhost:1234/v1): ").strip()
                    try:
                        mod = sys.modules.get("codex_cli_linker")
                        lm = getattr(mod, "list_models", list_models)
                        models = lm(base)
                        if models:
                            print(c("Available models:", BOLD))
                            pick = prompt_choice("Choose model", models)
                            ov["model"] = models[pick]
                        else:
                            warn("No models returned; leaving model empty.")
                    except Exception as e:
                        err(f"Model detection failed: {e}")
            elif idx == 2:
                # Context window: manual or auto-detect for current model
                mode = prompt_choice("Set context window", ["Enter value", "Auto-detect for current model", "Skip (no change)"])
                if mode == 0:
                    s = _safe_input("Context window (blank to skip): ").strip()
                    if s:
                        try:
                            ov["model_context_window"] = int(s)
                        except Exception:
                            pass
                else:
                    if mode == 2:
                        continue
                    base = (getattr(args, "base_url", "") or "").strip()
                    if not base:
                        base = _safe_input("Base URL for detection (e.g., http://localhost:1234/v1): ").strip()
                    model = (ov.get("model") or "").strip()
                    if not model:
                        try:
                            mod = sys.modules.get("codex_cli_linker")
                            lm = getattr(mod, "list_models", list_models)
                            models = lm(base)
                            if models:
                                pick = prompt_choice("Choose model", models)
                                model = models[pick]
                                ov["model"] = model
                        except Exception:
                            pass
                    try:
                        tacw = getattr(sys.modules.get("codex_cli_linker"), "try_auto_context_window", try_auto_context_window)
                        cw = tacw(base, model)
                        if cw > 0:
                            ov["model_context_window"] = cw
                            ok(f"Detected context window: {cw} tokens")
                        else:
                            warn("Could not detect context window; leaving unchanged.")
                    except Exception as e:
                        err(f"Context window detection failed: {e}")
            elif idx == 3:
                s = _safe_input("Max output tokens (blank to skip, 'null' to clear): ").strip()
                if s:
                    if _is_null_input(s):
                        ov["model_max_output_tokens"] = ""
                    else:
                        try:
                            ov["model_max_output_tokens"] = int(s)
                        except Exception:
                            pass
            elif idx == 4:
                i2 = prompt_choice(
                    "Approval policy",
                    ["untrusted", "on-failure", "on-request", "never", "Skip (no change)", "Set to null"],
                )
                if i2 < 4:
                    ov["approval_policy"] = [
                        "untrusted",
                        "on-failure",
                        "on-request",
                        "never",
                    ][i2]
                elif i2 == 5:
                    ov["approval_policy"] = ""
            elif idx == 5:
                i2 = prompt_choice(
                    "File opener",
                    ["vscode", "vscode-insiders", "windsurf", "cursor", "none", "Skip (no change)", "Set to null"],
                )
                if i2 < 5:
                    ov["file_opener"] = [
                        "vscode",
                        "vscode-insiders",
                        "windsurf",
                        "cursor",
                        "none",
                    ][i2]
                elif i2 == 6:
                    ov["file_opener"] = ""
            elif idx == 6:
                i2 = prompt_choice("Reasoning effort", ["minimal", "low", "medium", "high", "auto", "Skip (no change)", "Set to null"])
                if i2 < 5:
                    ov["model_reasoning_effort"] = ["minimal", "low", "medium", "high", "auto"][i2]
                elif i2 == 6:
                    ov["model_reasoning_effort"] = ""
            elif idx == 7:
                i2 = prompt_choice("Reasoning summary", ["auto", "concise", "detailed", "none", "Skip (no change)", "Set to null"])
                if i2 < 4:
                    ov["model_reasoning_summary"] = ["auto", "concise", "detailed", "none"][i2]
                elif i2 == 5:
                    ov["model_reasoning_summary"] = ""
            elif idx == 8:
                i2 = prompt_choice("Verbosity", ["low", "medium", "high", "Skip (no change)", "Set to null"])
                if i2 < 3:
                    ov["model_verbosity"] = ["low", "medium", "high"][i2]
                elif i2 == 4:
                    ov["model_verbosity"] = ""
            elif idx == 9:
                i2 = prompt_choice("Disable response storage", ["true", "false", "Skip (no change)", "Set to null"])
                if i2 < 2:
                    ov["disable_response_storage"] = True if i2 == 0 else False
                elif i2 == 3:
                    ov["disable_response_storage"] = ""
            elif idx == 10:
                i2 = prompt_choice("Sandbox mode", ["read-only", "workspace-write", "danger-full-access", "Skip (no change)", "Set to null"])
                if i2 < 3:
                    ov["sandbox_mode"] = ["read-only", "workspace-write", "danger-full-access"][i2]
                elif i2 == 4:
                    ov["sandbox_mode"] = ""
            elif idx == 11:
                s = _safe_input("ChatGPT base URL (blank to skip, 'null' to clear): ").strip()
                if s:
                    if _is_null_input(s):
                        ov["chatgpt_base_url"] = ""
                    else:
                        ov["chatgpt_base_url"] = s
            elif idx == 12:
                i2 = prompt_choice("Preferred auth method", ["apikey", "chatgpt", "Skip (no change)", "Set to null"])
                if i2 < 2:
                    ov["preferred_auth_method"] = ["apikey", "chatgpt"][i2]
                elif i2 == 3:
                    ov["preferred_auth_method"] = ""
            elif idx == 13:
                i2 = prompt_choice("Hide agent reasoning", ["true", "false", "Set to null"])
                if i2 == 2:
                    ov["hide_agent_reasoning"] = ""
                else:
                    ov["hide_agent_reasoning"] = True if i2 == 0 else False
            elif idx == 14:
                i2 = prompt_choice("Show raw agent reasoning", ["true", "false", "Set to null"])
                if i2 == 2:
                    ov["show_raw_agent_reasoning"] = ""
                else:
                    ov["show_raw_agent_reasoning"] = True if i2 == 0 else False
            elif idx == 15:
                i2 = prompt_choice("Model supports reasoning summaries", ["true", "false", "Set to null"])
                if i2 == 2:
                    ov["model_supports_reasoning_summaries"] = ""
                else:
                    ov["model_supports_reasoning_summaries"] = True if i2 == 0 else False
            elif idx == 16:
                i2 = prompt_choice("History persistence", ["save-all", "none", "Set to null"])
                if i2 == 2:
                    ov["history_persistence"] = ""
                else:
                    ov["history_persistence"] = ["save-all", "none"][i2]
            elif idx == 17:
                s = _safe_input("History max bytes (blank to skip, 'null' to clear): ").strip()
                if s:
                    if _is_null_input(s):
                        ov["history_max_bytes"] = ""
                    else:
                        try:
                            ov["history_max_bytes"] = int(s)
                        except Exception:
                            pass
            elif idx == 18:
                i2 = prompt_choice("tools.web_search", ["true", "false", "Set to null"])
                if i2 == 2:
                    ov["tools_web_search"] = ""
                else:
                    ov["tools_web_search"] = True if i2 == 0 else False
        elif act == 1:
            # Edit all fields in sequence
            ov["provider"] = _safe_input("Provider: ").strip() or ov.get("provider") or ""
            # Model sequence
            mode = prompt_choice("Set model", ["Enter manually", "Auto-detect from server"])
            if mode == 0:
                ov["model"] = _safe_input("Model: ").strip() or ov.get("model") or ""
            else:
                base = (getattr(args, "base_url", "") or "").strip()
                if not base:
                    base = _safe_input("Base URL for model list (e.g., http://localhost:1234/v1): ").strip()
                try:
                    mod = sys.modules.get("codex_cli_linker")
                    lm = getattr(mod, "list_models", list_models)
                    models = lm(base)
                    if models:
                        print(c("Available models:", BOLD))
                        pick = prompt_choice("Choose model", models)
                        ov["model"] = models[pick]
                except Exception as e:
                    err(f"Model detection failed: {e}")
            # Context window sequence
            mode_cw = prompt_choice("Set context window", ["Enter value", "Auto-detect for current model"])
            if mode_cw == 0:
                try:
                    ov["model_context_window"] = int(_safe_input("Context window: ").strip() or "0")
                except Exception:
                    pass
            else:
                base = (getattr(args, "base_url", "") or "").strip()
                if not base:
                    base = _safe_input("Base URL for detection (e.g., http://localhost:1234/v1): ").strip()
                model = (ov.get("model") or "").strip()
                if not model:
                    try:
                        mod = sys.modules.get("codex_cli_linker")
                        lm = getattr(mod, "list_models", list_models)
                        models = lm(base)
                        if models:
                            pick = prompt_choice("Choose model", models)
                            model = models[pick]
                            ov["model"] = model
                    except Exception:
                        pass
                try:
                    tacw = getattr(sys.modules.get("codex_cli_linker"), "try_auto_context_window", try_auto_context_window)
                    cw = tacw(base, model)
                    if cw > 0:
                        ov["model_context_window"] = cw
                        ok(f"Detected context window: {cw} tokens")
                except Exception as e:
                    err(f"Context window detection failed: {e}")
            # Max output tokens
            try:
                ov["model_max_output_tokens"] = int(_safe_input("Max output tokens: ").strip() or "0")
            except Exception:
                pass
            # Approval policy
            i2 = prompt_choice(
                "Approval policy",
                ["untrusted", "on-failure", "on-request", "never"],
            )
            ov["approval_policy"] = ["untrusted", "on-failure", "on-request", "never"][i2]
        elif act == 2:
            args.profile_overrides[name] = ov
            ok("Saved.")
            return
        elif act == 4:
            # Jump straight back to hub
            raise KeyboardInterrupt
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
        try:
            hub = prompt_choice(
                "Start with",
                [
                    "Manage profiles",
                    "Manage MCP servers",
                    "Manage providers",
                    "Manage global settings",
                    "Actions…",
                    "Legacy pipeline (guided)",
                    "Quit (no write)",
                ],
            )
        except KeyboardInterrupt:
            _handle_ctrlc_in_hub()
            continue
        if hub == 0:
            try:
                manage_profiles_interactive(args)
            except KeyboardInterrupt:
                # Return to hub on Ctrl-C inside sub-editors
                continue
            continue
        if hub == 1:
            try:
                manage_mcp_servers_interactive(args)
            except KeyboardInterrupt:
                continue
            continue
        if hub == 2:
            try:
                manage_providers_interactive(args)
            except KeyboardInterrupt:
                continue
            continue
        if hub == 4:
            # Actions submenu for write/launch
            try:
                act = prompt_choice(
                    "Action",
                    [
                        "Write",
                        "Overwrite + Write",
                        "Write and launch (print cmd)",
                        "Back",
                    ],
                )
            except KeyboardInterrupt:
                # Return to hub on Ctrl-C
                continue
            if act == 0:
                return "write"
            if act == 1:
                return "overwrite"
            if act == 2:
                return "write_and_launch"
            # Back to hub
            continue
        if hub == 5:
            return "legacy"
        if hub == 6:
            return "quit"
        items = [
            (
                "Profile name",
                args.profile or state.profile or state.provider or "<auto>",
            ),
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
        items.extend(
            [
                ("Approval policy", args.approval_policy),
                ("Sandbox mode", args.sandbox_mode),
                (
                    "Network access",
                    "true" if getattr(args, "network_access", None) else "false",
                ),
                (
                    "Exclude $TMPDIR",
                    (
                        "true"
                        if getattr(args, "exclude_tmpdir_env_var", None)
                        else "false"
                    ),
                ),
                (
                    "Exclude /tmp",
                    "true" if getattr(args, "exclude_slash_tmp", None) else "false",
                ),
                ("Writable roots (CSV)", getattr(args, "writable_roots", "") or ""),
                ("File opener", args.file_opener),
                ("Context window", str(args.model_context_window or 0)),
                ("Max output tokens", str(args.model_max_output_tokens or 0)),
                ("Reasoning effort", args.reasoning_effort),
                ("Reasoning summary", args.reasoning_summary),
                ("Verbosity", args.verbosity),
                ("Hide agent reasoning", "true" if getattr(args, "hide_agent_reasoning", False) else "false"),
                (
                    "Show raw agent reasoning",
                    "true" if getattr(args, "show_raw_agent_reasoning", False) else "false",
                ),
                (
                    "Model supports reasoning summaries",
                    "true"
                    if getattr(args, "model_supports_reasoning_summaries", False)
                    else "false",
                ),
                (
                    "Disable response storage",
                    "true" if args.disable_response_storage else "false",
                ),
                ("History persistence", "none" if args.no_history else "save-all"),
                ("History max bytes", str(args.history_max_bytes or 0)),
                ("Tools: web_search", "true" if args.tools_web_search else "false"),
                ("Wire API", getattr(args, "wire_api", "chat")),
                ("ChatGPT base URL", args.chatgpt_base_url or ""),
                ("Azure api-version", args.azure_api_version or ""),
                (
                    "Project doc max bytes",
                    str(getattr(args, "project_doc_max_bytes", 0) or 0),
                ),
                (
                    "HTTP headers (CSV KEY=VAL)",
                    ",".join(getattr(args, "http_header", []) or []) or "",
                ),
                (
                    "Env HTTP headers (CSV KEY=ENV)",
                    ",".join(getattr(args, "env_http_header", []) or []) or "",
                ),
                ("Notify (JSON array)", getattr(args, "notify", "") or ""),
                ("Instructions", args.instructions or ""),
                (
                    "Experimental resume",
                    getattr(args, "experimental_resume", "") or "",
                ),
                (
                    "Experimental instructions file",
                    getattr(args, "experimental_instructions_file", "") or "",
                ),
                (
                    "Experimental: use exec command tool",
                    "true"
                    if getattr(args, "experimental_use_exec_command_tool", False)
                    else "false",
                ),
                (
                    "Responses originator header override",
                    getattr(args, "responses_originator_header_internal_override", "")
                    or "",
                ),
                (
                    "Trusted projects (CSV)",
                    ",".join(getattr(args, "trust_project", []) or []) or "",
                ),
                ("Env key name", getattr(args, "env_key_name", "NULLKEY")),
                (
                    "TUI notifications",
                    (
                        "custom"
                        if getattr(args, "tui_notification_types", "")
                        else (
                            "true"
                            if getattr(args, "tui_notifications", None)
                            else "false"
                        )
                    ),
                ),
                (
                    "TUI notification types (CSV)",
                    getattr(args, "tui_notification_types", "") or "",
                ),
                ("Edit global config…", "open"),
                ("Manage profiles…", "open"),
                ("Manage MCP servers…", "open"),
            ]
        )
        for i, (label, val) in enumerate(items, 1):
            # Dim unchanged metadata for readability
            show = f"  {i}. {label}: {val}"
            print(
                c(show, GRAY)
                if "Manage" not in label
                and label not in ("Profile name", "Provider", "Base URL", "Model")
                else show
            )
        print()
        action_idx = prompt_choice(
            "Select edit action",
            [
                "Edit item (enter number)",
                "Edit all",
                "Go back",
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
                newprov = input(
                    "Provider id (e.g., lmstudio, ollama, openai, custom): "
                ).strip()
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
                    state.model = pick_model_interactive(
                        state.base_url, state.model or None
                    )
                except Exception as e:
                    err(str(e))
            elif label == "Edit global config…":
                _edit_global_all_fields(args, state)
            elif label == "Auth (OpenAI)":
                i2 = prompt_choice("OpenAI auth method", ["apikey", "chatgpt"])
                args.preferred_auth_method = "apikey" if i2 == 0 else "chatgpt"
            elif label == "API key (OPENAI_API_KEY)":
                # Set or update OPENAI_API_KEY in auth.json
                try:
                    new_key = getpass.getpass(
                        "Enter OPENAI_API_KEY (input hidden): "
                    ).strip()
                except Exception as exc:  # pragma: no cover
                    err(f"Could not read input: {exc}")
                    new_key = ""
                if new_key:
                    write_auth_json_merge(AUTH_JSON, {"OPENAI_API_KEY": new_key})
                    ok(f"Updated {AUTH_JSON} with OPENAI_API_KEY")
                    warn("Never commit this file; it contains a secret.")
            elif label == "Approval policy":
                i2 = prompt_choice("Choose", ["untrusted", "on-failure", "on-request", "never"])
                args.approval_policy = ["untrusted", "on-failure", "on-request", "never"][i2]
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
                i2 = prompt_choice(
                    "File opener",
                    ["vscode", "vscode-insiders", "windsurf", "cursor", "none"],
                )
                args.file_opener = [
                    "vscode",
                    "vscode-insiders",
                    "windsurf",
                    "cursor",
                    "none",
                ][i2]
            elif label == "Context window":
                try:
                    args.model_context_window = int(
                        input("Context window: ").strip() or "0"
                    )
                except Exception:
                    pass
            elif label == "Max output tokens":
                try:
                    args.model_max_output_tokens = int(
                        input("Max output tokens: ").strip() or "0"
                    )
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
            elif label == "Hide agent reasoning":
                i2 = prompt_choice("Hide agent reasoning", ["true", "false"])
                args.hide_agent_reasoning = True if i2 == 0 else False
            elif label == "Show raw agent reasoning":
                i2 = prompt_choice("Show raw agent reasoning", ["true", "false"])
                args.show_raw_agent_reasoning = True if i2 == 0 else False
            elif label == "Model supports reasoning summaries":
                i2 = prompt_choice(
                    "Model supports reasoning summaries", ["true", "false"]
                )
                args.model_supports_reasoning_summaries = True if i2 == 0 else False
            elif label == "Disable response storage":
                i2 = prompt_choice("Disable response storage", ["true", "false"])
                args.disable_response_storage = True if i2 == 0 else False
            elif label == "History persistence":
                i2 = prompt_choice("History persistence", ["save-all", "none"])
                args.no_history = True if i2 == 1 else False
            elif label == "History max bytes":
                try:
                    args.history_max_bytes = int(
                        input("History max bytes: ").strip() or "0"
                    )
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
            elif label == "Project doc max bytes":
                try:
                    args.project_doc_max_bytes = int(
                        input("Project doc max bytes: ").strip() or "0"
                    )
                except Exception:
                    pass
            elif label == "HTTP headers (CSV KEY=VAL)":
                raw = input("Headers CSV: ").strip()
                args.http_header = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Env HTTP headers (CSV KEY=ENV)":
                raw = input("Env headers CSV: ").strip()
                args.env_http_header = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Notify (JSON array)":
                # Expect a JSON array like ["-y", "mcp-server"] (quoted values)
                arr = _input_list_json("Notify (JSON array)", None)
                # Store as JSON string to preserve quoting; render will handle it
                try:
                    args.notify = _json.dumps(arr)
                except Exception:
                    args.notify = ""
            elif label == "Instructions":
                args.instructions = input("Instructions: ").strip()
            elif label == "Experimental resume":
                args.experimental_resume = input("Experimental resume: ").strip()
            elif label == "Experimental instructions file":
                args.experimental_instructions_file = input(
                    "Experimental instructions file: "
                ).strip()
            elif label == "Experimental: use exec command tool":
                i2 = prompt_choice("Use exec command tool", ["true", "false"])
                args.experimental_use_exec_command_tool = True if i2 == 0 else False
            elif label == "Responses originator header override":
                args.responses_originator_header_internal_override = input(
                    "Responses originator header override: "
                ).strip()
            elif label == "Trusted projects (CSV)":
                raw = input("Trusted projects CSV: ").strip()
                args.trust_project = [s.strip() for s in raw.split(",") if s.strip()]
            elif label == "Env key name":
                args.env_key_name = input("Env key name: ").strip() or args.env_key_name
            elif label == "TUI notifications":
                i2 = prompt_choice(
                    "TUI notifications", ["disabled", "enabled (all)", "filter types"]
                )
                if i2 == 0:
                    args.tui_notifications = False
                    args.tui_notification_types = ""
                elif i2 == 1:
                    args.tui_notifications = True
                    args.tui_notification_types = ""
                else:
                    args.tui_notifications = None
                    args.tui_notification_types = input(
                        "Types CSV (agent-turn-complete,approval-requested): "
                    ).strip()
            elif label == "TUI notification types (CSV)":
                args.tui_notification_types = input(
                    "Types CSV (agent-turn-complete,approval-requested): "
                ).strip()
            elif label == "Manage profiles…":
                manage_profiles_interactive(args)
            elif label == "Manage MCP servers…":
                manage_mcp_servers_interactive(args)
            continue
        elif action_idx == 1:
            # Edit all fields sequentially
            for idx in range(len(items)):
                label = items[idx][0]
                if label in ("Manage profiles…", "Manage MCP servers…"):
                    continue
                # Duplicate single-item edit flow for each label
                if label == "Profile name":
                    newp = input("Profile name: ").strip()
                    if newp:
                        args.profile = newp
                elif label == "Provider":
                    newprov = input(
                        "Provider id (e.g., lmstudio, ollama, openai, custom): "
                    ).strip()
                    if newprov:
                        args.provider = newprov
                        state.provider = newprov
                elif label == "Base URL":
                    state.base_url = pick_base_url(state, False)
                elif label == "Model":
                    if not state.base_url:
                        state.base_url = pick_base_url(state, False)
                    try:
                        state.model = pick_model_interactive(
                            state.base_url, state.model or None
                        )
                    except Exception as e:
                        err(str(e))
                elif label == "Edit global config…":
                    _edit_global_all_fields(args, state)
                elif label == "Auth (OpenAI)":
                    i2 = prompt_choice("OpenAI auth method", ["apikey", "chatgpt"])
                    args.preferred_auth_method = "apikey" if i2 == 0 else "chatgpt"
                elif label == "API key (OPENAI_API_KEY)":
                    try:
                        new_key = getpass.getpass(
                            "Enter OPENAI_API_KEY (input hidden): "
                        ).strip()
                    except Exception as exc:  # pragma: no cover
                        err(f"Could not read input: {exc}")
                        new_key = ""
                    if new_key:
                        write_auth_json_merge(AUTH_JSON, {"OPENAI_API_KEY": new_key})
                        ok(f"Updated {AUTH_JSON} with OPENAI_API_KEY")
                        warn("Never commit this file; it contains a secret.")
                elif label == "Approval policy":
                    i2 = prompt_choice("Choose", ["untrusted", "on-failure", "on-request", "never"])
                    args.approval_policy = ["untrusted", "on-failure", "on-request", "never"][i2]
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
                    i2 = prompt_choice(
                        "File opener",
                        ["vscode", "vscode-insiders", "windsurf", "cursor", "none"],
                    )
                    args.file_opener = [
                        "vscode",
                        "vscode-insiders",
                        "windsurf",
                        "cursor",
                        "none",
                    ][i2]
                elif label == "Context window":
                    try:
                        args.model_context_window = int(
                            input("Context window: ").strip() or "0"
                        )
                    except Exception:
                        pass
                elif label == "Max output tokens":
                    try:
                        args.model_max_output_tokens = int(
                            input("Max output tokens: ").strip() or "0"
                        )
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
                elif label == "Hide agent reasoning":
                    i2 = prompt_choice("Hide agent reasoning", ["true", "false"])
                    args.hide_agent_reasoning = True if i2 == 0 else False
                elif label == "Show raw agent reasoning":
                    i2 = prompt_choice("Show raw agent reasoning", ["true", "false"])
                    args.show_raw_agent_reasoning = True if i2 == 0 else False
                elif label == "Model supports reasoning summaries":
                    i2 = prompt_choice(
                        "Model supports reasoning summaries", ["true", "false"]
                    )
                    args.model_supports_reasoning_summaries = True if i2 == 0 else False
                elif label == "Disable response storage":
                    i2 = prompt_choice("Disable response storage", ["true", "false"])
                    args.disable_response_storage = True if i2 == 0 else False
                elif label == "History persistence":
                    i2 = prompt_choice("History persistence", ["save-all", "none"])
                    args.no_history = True if i2 == 1 else False
                elif label == "History max bytes":
                    try:
                        args.history_max_bytes = int(
                            input("History max bytes: ").strip() or "0"
                        )
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
                elif label == "Project doc max bytes":
                    try:
                        args.project_doc_max_bytes = int(
                            input("Project doc max bytes: ").strip() or "0"
                        )
                    except Exception:
                        pass
                elif label == "HTTP headers (CSV KEY=VAL)":
                    raw = input("Headers CSV: ").strip()
                    args.http_header = [s.strip() for s in raw.split(",") if s.strip()]
                elif label == "Env HTTP headers (CSV KEY=ENV)":
                    raw = input("Env headers CSV: ").strip()
                    args.env_http_header = [s.strip() for s in raw.split(",") if s.strip()]
                elif label == "Notify (JSON array)":
                    arr = _input_list_json("Notify (JSON array)")
                    try:
                        args.notify = _json.dumps(arr)
                    except Exception:
                        args.notify = ""
                elif label == "Instructions":
                    args.instructions = input("Instructions: ").strip()
                elif label == "Experimental resume":
                    args.experimental_resume = input("Experimental resume: ").strip()
                elif label == "Experimental instructions file":
                    args.experimental_instructions_file = input(
                        "Experimental instructions file: "
                    ).strip()
                elif label == "Experimental: use exec command tool":
                    i2 = prompt_choice("Use exec command tool", ["true", "false"])
                    args.experimental_use_exec_command_tool = True if i2 == 0 else False
                elif label == "Responses originator header override":
                    args.responses_originator_header_internal_override = input(
                        "Responses originator header override: "
                    ).strip()
                elif label == "Trusted projects (CSV)":
                    raw = input("Trusted projects CSV: ").strip()
                    args.trust_project = [s.strip() for s in raw.split(",") if s.strip()]
                elif label == "Env key name":
                    args.env_key_name = input("Env key name: ").strip() or args.env_key_name
                elif label == "TUI notifications":
                    i2 = prompt_choice(
                        "TUI notifications", ["disabled", "enabled (all)", "filter types"]
                    )
                    if i2 == 0:
                        args.tui_notifications = False
                        args.tui_notification_types = ""
                    elif i2 == 1:
                        args.tui_notifications = True
                        args.tui_notification_types = ""
                    else:
                        args.tui_notifications = None
                        args.tui_notification_types = input(
                            "Types CSV (agent-turn-complete,approval-requested): "
                        ).strip()
                elif label == "TUI notification types (CSV)":
                    args.tui_notification_types = input(
                        "Types CSV (agent-turn-complete,approval-requested): "
                    ).strip()
                elif label == "Manage profiles…":
                    manage_profiles_interactive(args)
                elif label == "Manage MCP servers…":
                    manage_mcp_servers_interactive(args)
            # Go back
            continue
        else:
            # Go back to main menu
            continue


def _input_list_csv(prompt: str, default: Optional[List[str]] = None) -> List[str]:
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _input_list_json(prompt: str, default: Optional[List[str]] = None) -> List[str]:
    """Read a JSON array like ["-y", "mcp-server"]. Requires quotes."""
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    try:
        arr = _json.loads(raw)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    # Fallback: treat as single token when parsing fails
    return [raw]


def _input_env_kv(
    prompt: str, default: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
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


def _parse_brace_kv(raw: str) -> Dict[str, str]:
    """Parse a curly-brace KV object like {k=v, a=b} into a dict.

    Accepts input with or without surrounding braces. Whitespace is trimmed.
    """
    s = (raw or "").strip()
    if not s:
        return {}
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: Dict[str, str] = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Values may be quoted; strip surrounding single or double quotes
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                if len(v) >= 2:
                    v = v[1:-1]
            if k:
                out[k] = v
    return out


def _print_item_with_desc(label: str, value: Any, desc: str) -> None:
    """Print a labeled value with a short description below it."""
    print(f"  {label}: {value}")
    if desc:
        print(c(f"     – {desc}", GRAY))


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
        i = prompt_choice(
            "Choose", ["Add server", "Edit server", "Remove server", "Go back", "Go back to main menu"]
        )
        if i == 0:
            name = input("Server name (identifier): ").strip()
            if not name:
                continue
            entry: Dict[str, Any] = {
                "command": "npx",
                "args": ["-y", "mcp-server"],
                "env": {},
            }
            _edit_mcp_entry_interactive(args, name, entry, creating=True)
        elif i == 1:
            if not names:
                warn("No servers to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            name = names[idx]
            curr = dict((args.mcp_servers or {}).get(name) or {})
            _edit_mcp_entry_interactive(
                args,
                name,
                curr or {"command": "npx", "args": ["-y", "mcp-server"], "env": {}},
                creating=False,
            )
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
        elif i == 4:
            # Return directly to main menu
            return
        else:
            break


def _edit_mcp_entry_interactive(
    args, name: str, entry: Dict[str, Any], creating: bool
) -> None:
    curr = dict(entry)
    while True:
        print()
        print(c(f"Edit MCP server [{name}]", BOLD))
        items = [
            ("Command", curr.get("command", "npx")),
            ("Args (JSON array)", _json.dumps(curr.get("args") or ["-y", "mcp-server"])),
            (
                "Env (CSV KEY=VAL)",
                ", ".join(f"{k}={v}" for k, v in (curr.get("env") or {}).items()),
            ),
            ("Startup timeout (ms)", str(curr.get("startup_timeout_ms", 10000))),
        ]
        for i, (lbl, val) in enumerate(items, 1):
            print(f"  {i}. {lbl}: {val}")
        act = prompt_choice("Action", ["Edit field", "Save", "Cancel", "Go back to main menu"])
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                curr["command"] = input("Command: ").strip() or curr.get(
                    "command", "npx"
                )
            elif idx == 1:
                curr["args"] = _input_list_json(
                    "Args JSON array (e.g., [\"-y\", \"mcp-server\"]): ",
                    curr.get("args") or ["-y", "mcp-server"],
                )
            elif idx == 2:
                curr["env"] = _input_env_kv(
                    "Env CSV (KEY=VAL,...): ", curr.get("env") or {}
                )
            elif idx == 3:
                try:
                    curr["startup_timeout_ms"] = int(
                        input("Startup timeout (ms): ").strip() or "10000"
                    )
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
        elif act == 3:
            # Jump back to hub
            raise KeyboardInterrupt
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
    "manage_providers_interactive",
]






def _default_env_key_for_profile(provider: str, profile: str) -> str:
    prov = (provider or 'custom').upper().replace('-', '_')
    prof = (profile or 'default').upper().replace('-', '_')
    return f"{prov}_{prof}_API_KEY"


def _default_base_for_provider_id(pid: str) -> str:
    """Return a sensible default base URL for a known provider id.

    Falls back to empty string when unknown or when the provider requires
    additional inputs (e.g., Azure).
    """
    pid = (pid or "").strip().lower()
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
    # Azure requires resource/path; leave blank to prompt later
    return mapping.get(pid, "")


def manage_providers_interactive(args) -> None:
    """Interactive manager for global model providers (add/edit/remove)."""
    if not hasattr(args, "providers_list") or args.providers_list is None:
        args.providers_list = []
    if not hasattr(args, "provider_overrides") or args.provider_overrides is None:
        args.provider_overrides = {}
    while True:
        print()
        print(c("Providers:", BOLD))
        # Build list from current provider, overrides and providers_list
        names = []
        if getattr(args, "provider", None):
            names.append(args.provider)
        for k in (getattr(args, "provider_overrides", {}) or {}).keys():
            if k not in names:
                names.append(k)
        for p in (getattr(args, "providers_list", []) or []):
            if p not in names:
                names.append(p)
        for n in names:
            ov = (args.provider_overrides or {}).get(n) or {}
            base = ov.get("base_url", "")
            print(f" - {n} {c(base, GRAY) if base else ''}")
        choice = prompt_choice(
            "Choose",
            [
                "Add provider",
                "Edit provider",
                "Remove provider",
                "Done",
            ],
        )
        if choice == 0:
            # Add provider: choose from presets or enter custom
            add_mode = prompt_choice("Add provider via", ["Choose preset", "Enter custom"])
            if add_mode == 0:
                # Build a stable list of known presets from PROVIDER_LABELS
                preset_ids = sorted(PROVIDER_LABELS.keys(), key=lambda k: PROVIDER_LABELS[k].lower())
                labels = []
                for pid0 in preset_ids:
                    default_base = _default_base_for_provider_id(pid0)
                    label = f"{PROVIDER_LABELS[pid0]} ({pid0})"
                    if default_base:
                        label += f"  [{default_base}]"
                    labels.append(label)
                labels.append("Go back to main menu")
                sel = prompt_choice("Preset", labels)
                if sel == len(labels) - 1:
                    # Return all the way back to the interactive hub
                    return
                chosen_pid = preset_ids[sel]
                # Allow renaming with prefilled name
                default_pid = chosen_pid
                pid = _safe_input(f"Provider id [{default_pid}]: ").strip() or default_pid
                # Default display name comes from preset label; allow editing
                default_name = PROVIDER_LABELS.get(chosen_pid, chosen_pid.capitalize())
                print(c("Display name — shown in tools and UIs.", GRAY))
                pname = _safe_input(f"Display name [{default_name}]: ").strip() or default_name
                # Base URL defaults to known value or prompts for Azure specifics
                if chosen_pid == "azure":
                    resource = _safe_input("Azure resource name (e.g., myres): ").strip()
                    print(c("Azure path — typically 'openai'.", GRAY))
                    path = _safe_input("Path (e.g., openai) [openai]: ").strip() or "openai"
                    base = f"https://{resource}.openai.azure.com/{path}" if resource else ""
                    # Ask for api-version for Azure preset
                    print(c("Azure api-version — required by Azure OpenAI (e.g., 2025-04-01-preview).", GRAY))
                    apiver = _safe_input("Azure api-version (e.g., 2025-04-01-preview) [skip to omit]: ").strip()
                else:
                    default_base = _default_base_for_provider_id(chosen_pid)
                    print(c("API base URL — OpenAI-compatible endpoint root (e.g., https://host:port/v1).", GRAY))
                    base = _safe_input(f"Base URL [{default_base}]: ").strip() or default_base
            else:
                pid = _safe_input("Provider id (e.g., openai, groq, custom): ").strip()
                if not pid:
                    continue
                print(c("Display name — shown in tools and UIs.", GRAY))
                pname = _safe_input("Display name (optional): ").strip() or pid.capitalize()
                print(c("API base URL — OpenAI-compatible endpoint root (e.g., https://host:port/v1).", GRAY))
                base = _safe_input("Base URL (blank to skip): ").strip()
            # Env key
            default_env = f"{pid.upper().replace('-', '_')}_API_KEY"
            print(c("Env key — name of environment variable that holds the API key.", GRAY))
            envk = _safe_input(f"Env key name [{default_env}]: ").strip() or default_env
            # Optional API key secret write
            try:
                secret = getpass.getpass(f"Enter API key for {pid} (env {envk}) [blank to skip]: ").strip()
            except Exception:
                secret = _safe_input(f"Enter API key for {pid} (env {envk}) [blank to skip]: ").strip()
            if secret:
                try:
                    import json as _json

                    write_auth_json_merge(AUTH_JSON, {envk: secret})
                    ok(f"Updated {AUTH_JSON} with {envk}")
                    warn("Never commit this file; it contains a secret.")
                except Exception as e:
                    err(f"Could not update {AUTH_JSON}: {e}")
            # Start override with required keys, plus optional display name
            override_entry = {"name": pname, "base_url": base, "env_key": envk}
            # Wire API choice (chat|responses); default "responses" for Azure else "chat"
            default_wire = "responses" if ((add_mode == 0 and chosen_pid == "azure") or pid == "azure") else "chat"
            print(c("Wire API — choose 'chat' (Chat Completions) or 'responses' (Responses API).", GRAY))
            wi = prompt_choice("Wire API", ["chat", "responses", "Skip (use default)"])
            if wi < 2:
                override_entry["wire_api"] = ["chat", "responses"][wi]
            # Query params: prefill Azure api-version if provided; allow editing
            qpi = {}
            if (add_mode == 0 and 'apiver' in locals() and apiver):
                qpi = {"api-version": apiver}
            # Let user add/override query params
            print(c("Query params — URL query parameters (e.g., api-version for Azure).", GRAY))
            qp_mode = prompt_choice("Query params", ["Keep defaults", "Edit ({key=\"value\",...})"])
            if qp_mode == 1:
                raw = _safe_input("Query params object (e.g., {api-version=\"2025-04-01-preview\"}): ").strip()
                if raw:
                    qpi = _parse_brace_kv(raw)
            if qpi:
                override_entry["query_params"] = qpi
            # HTTP headers: offer presets
            print(c("HTTP headers — add static or env-sourced headers to each request.", GRAY))
            hdr_mode = prompt_choice(
                "HTTP headers",
                [
                    "None",
                    "Preset: Azure api-key",
                    "Preset: Anthropic x-api-key",
                    "Preset: Authorization from env",
                    "Custom (CSV KEY=VAL)",
                ],
            )
            http_headers = {}
            env_http_headers = {}
            if hdr_mode == 1:
                env_http_headers = {"api-key": envk}
            elif hdr_mode == 2:
                env_http_headers = {"x-api-key": envk}
            elif hdr_mode == 3:
                env_http_headers = {"Authorization": envk}
            elif hdr_mode == 4:
                # CSV parsing: KEY=VAL,KEY2=VAL2 ; and KEY=ENVVAR, ... for env headers
                http_headers = _input_env_kv("HTTP headers CSV (KEY=VAL,...): ", {})
                env_http_headers = _input_env_kv("Env headers CSV (KEY=ENV,...): ", {})
            if http_headers:
                override_entry["http_headers"] = http_headers
            if env_http_headers:
                override_entry["env_http_headers"] = env_http_headers
            # Per-provider retry & stream settings
            try:
                rr = _safe_input(
                    f"Request max retries [{getattr(args, 'request_max_retries', 4)}]: "
                ).strip()
                if rr:
                    override_entry["request_max_retries"] = int(rr)
            except Exception:
                pass
            try:
                sr = _safe_input(
                    f"Stream max retries [{getattr(args, 'stream_max_retries', 10)}]: "
                ).strip()
                if sr:
                    override_entry["stream_max_retries"] = int(sr)
            except Exception:
                pass
            try:
                idle = _safe_input(
                    f"Stream idle timeout ms [{getattr(args, 'stream_idle_timeout_ms', 300000)}]: "
                ).strip()
                if idle:
                    override_entry["stream_idle_timeout_ms"] = int(idle)
            except Exception:
                pass
            args.provider_overrides[pid] = override_entry
            if pid not in args.providers_list and pid != getattr(args, "provider", None):
                args.providers_list.append(pid)
            ok(f"Saved provider '{pid}'")

        elif choice == 1:
            if not names:
                warn("No providers to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            pid = names[idx]
            # Loop inside this provider until save/cancel
            while True:
                ov = dict((args.provider_overrides or {}).get(pid) or {})
                print()
                print(c(f"Edit provider [{pid}]", BOLD))
                # Provider defaults
                df_name = PROVIDER_LABELS.get(pid, pid.capitalize())
                df_base = _default_base_for_provider_id(pid)
                df_env_map = {
                    "openai": "OPENAI_API_KEY",
                    "openrouter-remote": "OPENROUTER_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "azure": "AZURE_OPENAI_API_KEY",
                    "groq": "GROQ_API_KEY",
                    "mistral": "MISTRAL_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "cohere": "COHERE_API_KEY",
                    "baseten": "BASETEN_API_KEY",
                }
                df_env = df_env_map.get(pid, f"{pid.upper().replace('-', '_')}_API_KEY")
                df_wire = ov.get("wire_api") or ("responses" if pid == "azure" else getattr(args, "wire_api", "chat"))
                df_qp = ov.get("query_params") or ({"api-version": getattr(args, "azure_api_version", "")} if pid == "azure" and getattr(args, "azure_api_version", "") else {})
                df_req = getattr(args, "request_max_retries", 4)
                df_stream = getattr(args, "stream_max_retries", 10)
                df_idle = getattr(args, "stream_idle_timeout_ms", 300000)
                items = [
                    ("Display name", ov.get("name", df_name), f"Default: {df_name}"),
                    ("Base URL", ov.get("base_url", ""), f"Default: {df_base or '<requires input>'}"),
                    ("Env key", ov.get("env_key", ""), f"Default: {df_env}"),
                    ("Wire API", ov.get("wire_api", getattr(args, "wire_api", "chat")), f"Default: {df_wire}"),
                    ("Query params", ov.get("query_params", {}), f"Default: {df_qp if df_qp else '{}'}"),
                    ("HTTP headers", ov.get("http_headers", {}), "Default: {}"),
                    ("Env HTTP headers", ov.get("env_http_headers", {}), "Default: {}"),
                    ("Request max retries", str(ov.get("request_max_retries", df_req)), f"Default: {df_req}"),
                    ("Stream max retries", str(ov.get("stream_max_retries", df_stream)), f"Default: {df_stream}"),
                    ("Stream idle timeout ms", str(ov.get("stream_idle_timeout_ms", df_idle)), f"Default: {df_idle}"),
                ]
                for i2, (lbl, val, dsc) in enumerate(items, 1):
                    line = f"  {i2}. {lbl}: {val}"
                    if dsc:
                        line += " " + c(f"[{dsc}]", GRAY)
                    print(line)
                act = prompt_choice(
                    "Action",
                    [
                        "Edit field",
                        "Rename provider id",
                        "Save",
                        "Cancel",
                        "Go back to main menu",
                    ],
                )
                if act == 0:
                    s_in = _safe_input("Field number: ").strip()
                    if not s_in.isdigit():
                        continue
                    fi = int(s_in)
                    if fi == 1:
                        ov["name"] = _safe_input("Display name: ").strip() or ov.get("name", df_name)
                    elif fi == 2:
                        s2 = _safe_input("Base URL (blank=skip, 'null'=empty): ").strip()
                        if s2:
                            ov["base_url"] = "" if _is_null_input(s2) else s2
                    elif fi == 3:
                        s2 = _safe_input("Env key name (blank=skip, 'null'=empty): ").strip()
                        if s2:
                            ov["env_key"] = "" if _is_null_input(s2) else s2
                        try:
                            secret = getpass.getpass(f"Enter API key for {pid} (env {ov['env_key']}) [blank to skip]: ").strip()
                        except Exception:
                            secret = _safe_input(f"Enter API key for {pid} (env {ov['env_key']}) [blank to skip]: ").strip()
                        if secret:
                            write_auth_json_merge(AUTH_JSON, {ov["env_key"]: secret})
                            ok(f"Updated {AUTH_JSON} with {ov['env_key']}")
                            warn("Never commit this file; it contains a secret.")
                    elif fi == 4:
                        wi = prompt_choice(
                            "Wire API",
                            [
                                "chat",
                                "responses",
                                "Skip (no change)",
                                "Set to null",
                            ],
                        )
                        if wi < 2:
                            ov["wire_api"] = ["chat", "responses"][wi]
                        elif wi == 3:
                            ov["wire_api"] = ""
                    elif fi == 5:
                        raw = _safe_input("Query params object ({key=\"value\",...}) (blank=skip, 'null'=clear): ").strip()
                        if raw:
                            ov["query_params"] = {} if _is_null_input(raw) else _parse_brace_kv(raw)
                    elif fi == 6:
                        raw = _safe_input("HTTP headers CSV (KEY=VAL,...) (blank=skip, 'null'=clear): ").strip()
                        if raw:
                            if _is_null_input(raw):
                                ov["http_headers"] = {}
                            else:
                                env = {}
                                for pair in raw.split(','):
                                    if '=' in pair:
                                        k,v = pair.split('=',1)
                                        if k.strip():
                                            env[k.strip()] = v.strip()
                                ov["http_headers"] = env
                    elif fi == 7:
                        raw = _safe_input("Env headers CSV (KEY=ENV,...) (blank=skip, 'null'=clear): ").strip()
                        if raw:
                            if _is_null_input(raw):
                                ov["env_http_headers"] = {}
                            else:
                                env = {}
                                for pair in raw.split(','):
                                    if '=' in pair:
                                        k,v = pair.split('=',1)
                                        if k.strip():
                                            env[k.strip()] = v.strip()
                                ov["env_http_headers"] = env
                    elif fi == 8:
                        s2 = _safe_input("Request max retries (blank=skip, 'null'=clear): ").strip()
                        if s2:
                            if _is_null_input(s2):
                                ov["request_max_retries"] = ""
                            else:
                                try:
                                    ov["request_max_retries"] = int(s2)
                                except Exception:
                                    pass
                    elif fi == 9:
                        s2 = _safe_input("Stream max retries (blank=skip, 'null'=clear): ").strip()
                        if s2:
                            if _is_null_input(s2):
                                ov["stream_max_retries"] = ""
                            else:
                                try:
                                    ov["stream_max_retries"] = int(s2)
                                except Exception:
                                    pass
                    elif fi == 10:
                        s2 = _safe_input("Stream idle timeout ms (blank=skip, 'null'=clear): ").strip()
                        if s2:
                            if _is_null_input(s2):
                                ov["stream_idle_timeout_ms"] = ""
                            else:
                                try:
                                    ov["stream_idle_timeout_ms"] = int(s2)
                                except Exception:
                                    pass
                    # keep editing loop
                    args.provider_overrides[pid] = ov
                    continue
                elif act == 1:
                    new_id = _safe_input(f"New provider id for '{pid}' (blank to cancel): ").strip()
                    if new_id and new_id != pid:
                        existing = set((args.provider_overrides or {}).keys()) | set(args.providers_list or [])
                        if new_id in existing:
                            warn(f"Provider id '{new_id}' already exists; rename cancelled.")
                        else:
                            (args.provider_overrides or {})[new_id] = ov
                            (args.provider_overrides or {}).pop(pid, None)
                            args.providers_list = [new_id if x == pid else x for x in (args.providers_list or [])]
                            if getattr(args, 'provider', None) == pid:
                                args.provider = new_id
                            pmap = getattr(args, 'profile_overrides', {}) or {}
                            for pname, pov in pmap.items():
                                if isinstance(pov, dict) and (pov.get('provider') or '') == pid:
                                    pov['provider'] = new_id
                            ok(f"Renamed provider id '{pid}' -> '{new_id}'")
                            pid = new_id
                    continue
                elif act == 2:
                    args.provider_overrides[pid] = ov
                    ok("Saved.")
                    break
                elif act == 4:
                    # Jump straight back to hub
                    return
                else:
                    break

        elif choice == 2:
            if not names:
                warn("No providers to remove.")
                continue
            idx = prompt_choice("Remove which?", names)
            pid = names[idx]
            if pid == getattr(args, "provider", None):
                warn("Won't remove the current active provider; change provider first.")
                continue
            if prompt_yes_no(f"Remove provider '{pid}'?", default=False):
                (args.provider_overrides or {}).pop(pid, None)
                if pid in (args.providers_list or []):
                    args.providers_list = [p for p in args.providers_list if p != pid]
                info(f"Removed provider: {pid}")
            else:
                info("Removal cancelled.")
        else:
            break
