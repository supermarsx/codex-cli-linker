from __future__ import annotations

import sys
from ..prompts import pick_base_url, prompt_choice
from ..utils import resolve_provider
from ..ui import c, CYAN
from ..keychain import store_api_key_in_keychain
from ..logging_utils import log_event


def determine_base_and_provider(args, state) -> None:
    """Resolve base URL and provider using the same logic as before."""
    picker = getattr(
        sys.modules.get("codex_cli_linker"), "pick_base_url", pick_base_url
    )
    preferred_provider = (args.provider or "").strip().lower()
    if args.full_auto:
        if preferred_provider == "openai" and not args.base_url:
            from ..spec import DEFAULT_OPENAI

            base = DEFAULT_OPENAI
        else:
            if args.auto:
                base = args.base_url or picker(state, True)
            else:
                if getattr(args, "yes", False) and not args.base_url:
                    from ..ui import err

                    err("--yes provided but no --base-url; refusing to prompt.")
                    raise SystemExit(2)
                base = args.base_url or picker(state, False)
        state.base_url = base
    else:
        if args.auto:
            base = args.base_url or picker(state, True)
            state.base_url = base
        else:
            state.base_url = args.base_url or state.base_url or ""

    default_provider = resolve_provider(state.base_url or "")
    state.provider = args.provider or default_provider
    if state.provider == "openai" and not state.base_url:
        from ..spec import DEFAULT_OPENAI

        state.base_url = DEFAULT_OPENAI
    if state.provider == "custom":
        if not (args.full_auto or args.auto or getattr(args, "yes", False)):
            state.provider = (
                input(
                    "Provider id to use in model_providers (e.g., myprovider): "
                ).strip()
                or "custom"
            )


def maybe_prompt_openai_auth_method(args, state) -> None:
    """For interactive OpenAI runs, prompt for auth method selection."""
    if state.provider == "openai" and not args.auto and not getattr(args, "yes", False):
        print()
        print(c("OpenAI authentication method:", CYAN))
        idx = prompt_choice(
            "Select",
            [
                "API key (preferred_auth_method=apikey)",
                "ChatGPT (preferred_auth_method=chatgpt)",
            ],
        )
        args.preferred_auth_method = "apikey" if idx == 0 else "chatgpt"


def set_profile_and_api_key(args, state) -> None:
    """Set profile, api key, keychain storage, and env key defaults."""
    if args.provider:
        state.profile = args.profile or args.provider
    else:
        state.profile = args.profile or state.profile or state.provider
    state.api_key = args.api_key or state.api_key or "sk-local"
    if args.api_key and args.keychain and args.keychain != "none":
        success = store_api_key_in_keychain(args.keychain, state.env_key, args.api_key)
        log_event(
            "keychain_store",
            provider=state.provider,
            path=state.env_key,
            error_type=None if success else "store_failed",
        )
    if "env_key_name" in getattr(args, "_explicit", set()):
        state.env_key = args.env_key_name
    else:
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
        if not state.env_key or state.env_key == "NULLKEY":
            state.env_key = default_envs.get(state.provider, state.env_key or "NULLKEY")


def maybe_prompt_and_store_openai_key(args, home) -> None:
    """Interactive OpenAI API key prompt/writing (delegates to auth_flow)."""
    from ..auth_flow import maybe_prompt_openai_key

    try:
        maybe_prompt_openai_key(args, home)
    except SystemExit:
        raise
    except Exception:
        pass
