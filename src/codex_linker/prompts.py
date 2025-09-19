from __future__ import annotations

import inspect
import sys
from typing import List, Optional

from .spec import DEFAULT_LMSTUDIO, DEFAULT_OLLAMA
from .detect import detect_base_url, list_models
from .state import LinkerState
from .ui import err, c, BOLD, CYAN, info, warn


def prompt_choice(prompt: str, options: List[str]) -> int:
    """Display a numbered list and return the selected zero-based index."""
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


__all__ = [
    "prompt_choice",
    "prompt_yes_no",
    "pick_base_url",
    "pick_model_interactive",
    "interactive_prompts",
]
