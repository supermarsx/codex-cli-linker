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
            "writable_roots": [p.strip() for p in (getattr(args, "writable_roots", "") or "").split(",") if p.strip()],
            "network_access": bool(args.network_access) if args.network_access is not None else False,
            "exclude_tmpdir_env_var": bool(args.exclude_tmpdir_env_var) if getattr(args, "exclude_tmpdir_env_var", None) is not None else False,
            "exclude_slash_tmp": bool(args.exclude_slash_tmp) if getattr(args, "exclude_slash_tmp", None) is not None else False,
        },
        "model_reasoning_effort": args.reasoning_effort,
        "model_reasoning_summary": args.reasoning_summary,
        "model_verbosity": args.verbosity,
        "profile": args.profile or state.profile,
        "model_context_window": args.model_context_window or 0,
        "model_max_output_tokens": args.model_max_output_tokens or 0,
        "project_doc_max_bytes": args.project_doc_max_bytes,
        "tui": {
            "style": args.tui,
        },
        "notify": None,
        "instructions": args.instructions,
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
                "wire_api": getattr(args, "wire_api", "chat"),
                "env_key": state.env_key or "NULLKEY",
                "request_max_retries": args.request_max_retries,
                "stream_max_retries": args.stream_max_retries,
                "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
                "http_headers": {},
                "env_http_headers": {},
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
            "wire_api": getattr(args, "wire_api", "chat"),
            "env_key": state.env_key,
            "request_max_retries": args.request_max_retries,
            "stream_max_retries": args.stream_max_retries,
            "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
            "http_headers": {},
            "env_http_headers": {},
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
    # Optional: MCP servers (top-level key mcp_servers)
    mcp = getattr(args, "mcp_servers", None) or {}
    if isinstance(mcp, dict) and mcp:
        # Minimal normalization: ensure args list for each server when string provided
        norm: Dict[str, Any] = {}
        for name, entry in mcp.items():
            if not isinstance(entry, dict):
                continue
            cmd = entry.get("command") or "npx"
            a = entry.get("args")
            if isinstance(a, str):
                a_list = [s.strip() for s in a.split(",") if s.strip()]
            else:
                a_list = list(a or [])
            env = entry.get("env") or {}
            out: Dict[str, Any] = {"command": cmd, "args": a_list, "env": env}
            if isinstance(entry.get("startup_timeout_ms"), int):
                out["startup_timeout_ms"] = int(entry["startup_timeout_ms"])  # type: ignore[index]
            cfg.setdefault("mcp_servers", {})[name] = out
        # If none valid after normalization, do not emit key
    # TUI notifications: boolean or array of allowed types
    allowed_types = {"agent-turn-complete", "approval-requested"}
    tnt = getattr(args, "tui_notification_types", "") or ""
    types: list[str] = [s.strip() for s in tnt.split(",") if s.strip()] if tnt else []
    types = [t for t in types if t in allowed_types]
    if types:
        cfg["tui"]["notifications"] = types
    elif getattr(args, "tui_notifications", None) is not None:
        cfg["tui"]["notifications"] = bool(args.tui_notifications)

    # Parse notify as CSV or JSON array
    notify_raw = getattr(args, "notify", "") or ""
    if notify_raw:
        try:
            import json as _json

            if notify_raw.strip().startswith("["):
                arr = _json.loads(notify_raw)
                if isinstance(arr, list) and arr:
                    cfg["notify"] = arr
            else:
                arr = [s.strip() for s in notify_raw.split(",") if s.strip()]
                if arr:
                    cfg["notify"] = arr
        except Exception:
            pass
    # HTTP headers
    headers_list = getattr(args, "http_header", []) or []
    hmap: Dict[str, Any] = {}
    for item in headers_list:
        if "=" in str(item):
            k, v = str(item).split("=", 1)
            if k.strip():
                hmap[k.strip()] = v.strip()
    if hmap:
        cfg["model_providers"][args.provider or state.provider]["http_headers"] = hmap
    env_headers_list = getattr(args, "env_http_header", []) or []
    ehmap: Dict[str, Any] = {}
    for item in env_headers_list:
        if "=" in str(item):
            k, v = str(item).split("=", 1)
            if k.strip():
                ehmap[k.strip()] = v.strip()
    if ehmap:
        cfg["model_providers"][args.provider or state.provider]["env_http_headers"] = ehmap
    # Trusted projects
    trusts = getattr(args, "trust_project", []) or []
    if trusts:
        cfg["projects"] = {p: {"trust_level": "trusted"} for p in trusts}
    return cfg


__all__ = ["build_config_dict"]
