"""Argument definitions: Provider presets and provider-specific flags.

This module defines provider selection, preset shortcuts, HTTP header flags,
wire protocol, and retry settings. It also exposes SetProviderAction used to
implement handy provider preset switches.
"""

from __future__ import annotations

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
    """Argparse action for convenient provider preset flags.

    When invoked it sets provider id, optionally preferred auth method, and a
    default base URL when appropriate.
    """

    def __init__(self, option_strings, dest, nargs=0, **kwargs):
        self.provider_id = kwargs.pop("provider_id", None)
        self.set_auth = kwargs.pop("set_auth", None)
        self.use_default_base = kwargs.pop("use_default_base", True)
        super().__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, "provider", self.provider_id)
        if self.set_auth:
            setattr(namespace, "preferred_auth_method", self.set_auth)
        try:
            base = getattr(namespace, "base_url", None)
        except Exception:
            base = None
        if (not base) and self.use_default_base:
            default_base = _default_base_for_provider_id(self.provider_id or "")
            if default_base:
                setattr(namespace, "base_url", default_base)
        setattr(namespace, self.dest, True)


def _has_option(p, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_provider_args(p):
    """Attach provider preset/flags to the parser."""
    if _has_option(p, "-P"):
        return
    providers = p.add_argument_group("Providers")
    providers.add_argument(
        "-P",
        "--provider",
        help="Provider id (model_providers.<id>), default deduced",
    )
    # Preset convenience flags (locals)
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


__all__ = ["add_provider_args", "SetProviderAction"]
