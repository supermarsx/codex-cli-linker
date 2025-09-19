"""Config shaping utilities."""

from __future__ import annotations
import argparse
from typing import Any, Dict

from .state import LinkerState
from .spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_OPENROUTER_LOCAL,
    PROVIDER_LABELS,
)
from .utils import resolve_provider


def build_config_dict(state: LinkerState, args: argparse.Namespace) -> Dict:
    """Translate runtime selections into a config dict matching the TOML spec."""
    # Use ``Any`` for nested values so mypy doesn't complain about deep indexing
    # within the configuration structure.
    resolved = resolve_provider(state.base_url)
    cfg: Dict[str, Any] = {
        "model": args.model or state.model or "gpt-5",
        "model_provider": args.provider or state.provider,
        "approval_policy": args.approval_policy,
        "sandbox_mode": args.sandbox_mode,
        "file_opener": args.file_opener,
        "sandbox_workspace_write": {
            "writable_roots": [],
            "network_access": False,
            "exclude_tmpdir_env_var": False,
            "exclude_slash_tmp": False,
        },
        "model_reasoning_effort": args.reasoning_effort,
        "model_reasoning_summary": args.reasoning_summary,
        "model_verbosity": args.verbosity,
        "profile": args.profile or state.profile,
        "model_context_window": args.model_context_window or 0,
        "model_max_output_tokens": args.model_max_output_tokens or 0,
        "project_doc_max_bytes": args.project_doc_max_bytes,
        "tui": args.tui,
        "hide_agent_reasoning": args.hide_agent_reasoning,
        "show_raw_agent_reasoning": args.show_raw_agent_reasoning,
        "model_supports_reasoning_summaries": args.model_supports_reasoning_summaries,
        "chatgpt_base_url": args.chatgpt_base_url,
        "experimental_resume": args.experimental_resume,
        "experimental_instructions_file": args.experimental_instructions_file,
        "experimental_use_exec_command_tool": args.experimental_use_exec_command_tool,
        "responses_originator_header_internal_override": args.responses_originator_header_internal_override,
        "preferred_auth_method": args.preferred_auth_method,
        "tools": {"web_search": bool(args.tools_web_search)},
        "disable_response_storage": args.disable_response_storage,
        "history": {
            "persistence": "save-all" if not args.no_history else "none",
            "max_bytes": args.history_max_bytes,
        },
        "model_providers": {
            (args.provider or state.provider): {
                "name": PROVIDER_LABELS.get(
                    resolved,
                    resolved.capitalize(),
                ),
                "base_url": state.base_url.rstrip("/"),
                "wire_api": "chat",
                "api_key_env_var": state.env_key or "NULLKEY",
                "request_max_retries": args.request_max_retries,
                "stream_max_retries": args.stream_max_retries,
                "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
            }
        },
        "profiles": {
            (args.profile or state.profile): {
                "model": args.model or state.model or "gpt-5",
                "model_provider": args.provider or state.provider,
                "model_context_window": args.model_context_window or 0,
                "model_max_output_tokens": args.model_max_output_tokens or 0,
                "approval_policy": args.approval_policy,
            }
        },
    }
    if args.azure_api_version:
        cfg["model_providers"][args.provider or state.provider]["query_params"] = {
            "api-version": args.azure_api_version
        }
    extra = getattr(args, "providers_list", []) or []
    for pid in [p for p in extra if p and p != state.provider]:
        if pid.lower() == "lmstudio":
            base_u = DEFAULT_LMSTUDIO
            name = "LM Studio"
        elif pid.lower() == "ollama":
            base_u = DEFAULT_OLLAMA
            name = "Ollama"
        elif pid.lower() == "vllm":
            base_u = DEFAULT_VLLM
            name = PROVIDER_LABELS.get("vllm", "vLLM")
        elif pid.lower() == "tgwui":
            base_u = DEFAULT_TGWUI
            name = PROVIDER_LABELS.get("tgwui", "Text-Gen-WebUI")
        elif pid.lower() == "tgi":
            base_u = DEFAULT_TGI_8080
            name = PROVIDER_LABELS.get("tgi", "TGI")
        elif pid.lower() == "openrouter":
            base_u = DEFAULT_OPENROUTER_LOCAL
            name = PROVIDER_LABELS.get("openrouter", "OpenRouter Local")
        elif pid.lower() in ("jan", "llamafile", "gpt4all", "local"):
            base_u = args.base_url or state.base_url or DEFAULT_LMSTUDIO
            name = PROVIDER_LABELS.get(pid.lower(), pid.capitalize())
        else:
            base_u = args.base_url or state.base_url or DEFAULT_LMSTUDIO
            name = pid.capitalize()
        cfg["model_providers"][pid] = {
            "name": name,
            "base_url": base_u.rstrip("/"),
            "wire_api": "chat",
            "api_key_env_var": state.env_key,
            "request_max_retries": args.request_max_retries,
            "stream_max_retries": args.stream_max_retries,
            "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
        }
        if args.azure_api_version and pid not in ("lmstudio", "ollama"):
            cfg["model_providers"][pid]["query_params"] = {
                "api-version": args.azure_api_version
            }
        cfg["profiles"][pid] = {
            "model": args.model or state.model or "gpt-5",
            "model_provider": pid,
            "model_context_window": args.model_context_window or 0,
            "model_max_output_tokens": args.model_max_output_tokens or 0,
            "approval_policy": args.approval_policy,
        }
    return cfg


__all__ = ["build_config_dict"]
