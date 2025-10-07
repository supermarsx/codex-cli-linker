"""Base URL and model pickers used by interactive flows.

Includes:
- ``pick_base_url``: menu-driven or auto-detect selection of an OpenAI-compatible
  base URL (with Azure conveniences)
- ``pick_model_interactive``: simple model chooser using ``/models``
- ``interactive_prompts``: compact prompts for core UX settings (approval,
  reasoning effort/summary, verbosity)
"""

from __future__ import annotations

import inspect
import sys
from typing import Optional

from ..spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_OPENAI,
    DEFAULT_OPENROUTER,
    DEFAULT_ANTHROPIC,
    DEFAULT_GROQ,
    DEFAULT_MISTRAL,
    DEFAULT_DEEPSEEK,
    DEFAULT_COHERE,
    DEFAULT_BASETEN,
    DEFAULT_KOBOLDCPP,
)
from ..detect import detect_base_url, list_models
from ..state import LinkerState
from ..ui import c, BOLD, CYAN
from .input_utils import prompt_choice


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
    """Return a base URL via auto-detect or interactive presets/custom entry.

    When ``auto`` is True, delegates to ``detect_base_url`` and falls back to
    the last saved value or LM Studio default. Otherwise presents a menu of
    common providers plus a custom entry and an Azure resource/path helper.
    """
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
    if choice.startswith("OpenRouter (") and "remote" not in choice:
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
    if choice.startswith("Azure"):
        # Ask the user for resource + path (usually 'openai')
        resource = input("Azure resource name (e.g., myres): ").strip()
        path = input("Path (e.g., openai) [openai]: ").strip() or "openai"
        return f"https://{resource}.openai.azure.com/{path}"
    if choice.startswith("Use last saved"):
        return state.base_url
    # Custom or default
    return input("Base URL: ").strip()


def pick_model_interactive(base_url: str, last: Optional[str]) -> str:
    """List models from ``base_url`` and prompt for a selection.

    Highlights the ``last`` model when provided to make re-selection easy.
    """
    mod = sys.modules.get("codex_cli_linker")
    lm = getattr(mod, "list_models", list_models)
    models = lm(base_url)
    print(c("Available models:", BOLD))
    labels = [m + (c("  (last)", CYAN) if m == last else "") for m in models]
    idx = prompt_choice("Pick a model", labels)
    return models[idx]


def interactive_prompts(args) -> None:
    """Prompt for core UX settings (approval, reasoning, verbosity).

    Keeps choices minimal and maps free-form selections to supported values.
    """
    # Approval policy
    ap_opts = ["untrusted", "on-failure"]
    print()
    print(c("Approval policy:", BOLD))
    i = prompt_choice("Choose approval mode", ap_opts)
    args.approval_policy = ap_opts[i]

    # Reasoning effort
    re_opts_full = ["minimal", "low", "medium", "high", "auto"]
    print()
    print(c("Reasoning effort:", BOLD))
    i = prompt_choice("Choose reasoning effort", re_opts_full)
    chosen_eff = re_opts_full[i]
    if chosen_eff not in ("minimal", "low"):
        chosen_eff = "low" if chosen_eff in ("medium", "high", "auto") else "minimal"
    args.reasoning_effort = chosen_eff

    # Reasoning summary
    rs_opts = ["auto", "concise"]
    print()
    print(c("Reasoning summary:", BOLD))
    i = prompt_choice("Choose reasoning summary", rs_opts)
    args.reasoning_summary = rs_opts[i]

    # Verbosity
    vb_opts = ["low", "medium"]
    print()
    print(c("Model verbosity:", BOLD))
    i = prompt_choice("Choose verbosity", vb_opts)
    args.verbosity = vb_opts[i]
