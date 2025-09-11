"""Config rendering utilities (TOML/JSON/YAML) and shaping."""

from __future__ import annotations
import argparse
import json
import re
from typing import Dict, List

from .state import LinkerState
from .spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
    PROVIDER_LABELS,
)


def build_config_dict(state: LinkerState, args: argparse.Namespace) -> Dict:
    """Translate runtime selections into a config dict matching the TOML spec."""
    cfg: Dict[str, object] = {
        "model": args.model or state.model or "gpt-5",
        "model_provider": state.provider,
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
        "profile": state.profile,
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
            state.provider: {
                "name": (
                    "LM Studio"
                    if state.base_url.startswith("http://localhost:1234")
                    else (
                        "Ollama"
                        if state.base_url.startswith("http://localhost:11434")
                        else (
                            "vLLM"
                            if state.base_url.startswith("http://localhost:8000")
                            else (
                                "Text-Gen-WebUI"
                                if state.base_url.startswith("http://localhost:5000")
                                else (
                                    "TGI"
                                    if (
                                        state.base_url.startswith("http://localhost:8080")
                                        or state.base_url.startswith("http://localhost:3000")
                                    )
                                    else (
                                        "OpenRouter Local"
                                        if state.base_url.startswith("http://localhost:7000")
                                        else PROVIDER_LABELS.get(
                                            state.provider, state.provider.capitalize()
                                        )
                                    )
                                )
                            )
                        )
                    )
                ),
                "base_url": state.base_url.rstrip("/"),
                "wire_api": "chat",
                "api_key_env_var": state.env_key,
                "request_max_retries": args.request_max_retries,
                "stream_max_retries": args.stream_max_retries,
                "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
            }
        },
        "profiles": {
            state.profile: {
                "model": args.model or state.model or "gpt-5",
                "model_provider": state.provider,
                "model_context_window": args.model_context_window or 0,
                "model_max_output_tokens": args.model_max_output_tokens or 0,
                "approval_policy": args.approval_policy,
            }
        },
    }
    if args.azure_api_version:
        cfg["model_providers"][state.provider]["query_params"] = {
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


def to_toml(cfg: Dict) -> str:
    """Purpose-built TOML emitter for this config shape."""

    def is_empty(v) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict)):
            return len(v) == 0
        return False

    lines: List[str] = []
    lines.append("# Generated by codex-cli-linker")

    def w(key: str, val):
        if key == "tui":
            return
        if is_empty(val):
            return
        if isinstance(val, bool):
            sval = "true" if val else "false"
        elif isinstance(val, (int, float)):
            sval = str(val)
        else:
            sval = json.dumps(val)
        lines.append(f"{key} = {sval}")

    w("model", cfg.get("model"))
    w("model_provider", cfg.get("model_provider"))
    w("approval_policy", cfg.get("approval_policy"))
    w("sandbox_mode", cfg.get("sandbox_mode"))
    w("file_opener", cfg.get("file_opener"))
    w("model_reasoning_effort", cfg.get("model_reasoning_effort"))
    w("model_reasoning_summary", cfg.get("model_reasoning_summary"))
    w("model_verbosity", cfg.get("model_verbosity"))
    w("model_context_window", cfg.get("model_context_window"))
    w("model_max_output_tokens", cfg.get("model_max_output_tokens"))
    w("project_doc_max_bytes", cfg.get("project_doc_max_bytes"))
    w("tui", cfg.get("tui"))
    w("hide_agent_reasoning", cfg.get("hide_agent_reasoning"))
    w("show_raw_agent_reasoning", cfg.get("show_raw_agent_reasoning"))
    w("model_supports_reasoning_summaries", cfg.get("model_supports_reasoning_summaries"))
    w("chatgpt_base_url", cfg.get("chatgpt_base_url"))
    w("experimental_resume", cfg.get("experimental_resume"))
    w("experimental_instructions_file", cfg.get("experimental_instructions_file"))
    w("experimental_use_exec_command_tool", cfg.get("experimental_use_exec_command_tool"))
    w(
        "responses_originator_header_internal_override",
        cfg.get("responses_originator_header_internal_override"),
    )
    w("preferred_auth_method", cfg.get("preferred_auth_method"))
    w("profile", cfg.get("profile"))
    w("disable_response_storage", cfg.get("disable_response_storage"))

    tools = cfg.get("tools") or {}
    tools_filtered = {k: v for k, v in tools.items() if not is_empty(v)}
    if tools_filtered:
        lines.append("")
        lines.append("[tools]")
        for k, v in tools_filtered.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f"{k} = {json.dumps(v)}")

    hist = cfg.get("history") or {}
    hist_filtered = {k: v for k, v in hist.items() if not is_empty(v)}
    if hist_filtered:
        lines.append("")
        lines.append("[history]")
        if "persistence" in hist_filtered:
            lines.append(f"persistence = {json.dumps(hist_filtered['persistence'])}")
        if "max_bytes" in hist_filtered:
            lines.append(f"max_bytes = {hist_filtered['max_bytes']}")

    sww = cfg.get("sandbox_workspace_write") or {}
    sww_filtered = {k: v for k, v in sww.items() if not is_empty(v)}
    if sww_filtered:
        lines.append("")
        lines.append("[sandbox_workspace_write]")
        for k, val in sww_filtered.items():
            if isinstance(val, list):
                if not val:
                    continue
                arr = ", ".join(json.dumps(x) for x in val if not is_empty(x))
                if arr.strip():
                    lines.append(f"{k} = [ {arr} ]")
            elif isinstance(val, bool):
                lines.append(f"{k} = {'true' if val else 'false'}")
            elif isinstance(val, (int, float)):
                lines.append(f"{k} = {val}")
            else:
                if not is_empty(val):
                    lines.append(f"{k} = {json.dumps(val)}")

    providers = cfg.get("model_providers") or {}
    for pid, p in providers.items():
        pf = {k: v for k, v in p.items() if not is_empty(v)}
        if "query_params" in pf and is_empty(pf["query_params"]):
            pf.pop("query_params", None)
        if not pf:
            continue
        section_lines = []
        for k in ("name", "base_url", "wire_api", "api_key_env_var"):
            if k in pf:
                section_lines.append(f"{k} = {json.dumps(pf[k])}")
        for k in ("request_max_retries", "stream_max_retries", "stream_idle_timeout_ms"):
            if k in pf:
                section_lines.append(f"{k} = {pf[k]}")
        if (
            "query_params" in pf
            and isinstance(pf["query_params"], dict)
            and pf["query_params"]
        ):
            qp_items = ", ".join(
                f"{json.dumps(k)} = {json.dumps(v)}"
                for k, v in pf["query_params"].items()
                if not is_empty(v)
            )
            if qp_items:
                section_lines.append(f"query_params = {{ {qp_items} }}")
        if section_lines:
            lines.append("")
            lines.append(f"[model_providers.{pid}]")
            lines.extend(section_lines)

    profiles = cfg.get("profiles") or {}
    for name, pr in profiles.items():
        prf = {k: v for k, v in pr.items() if not is_empty(v)}
        if not prf:
            continue
        section_lines = []
        for k in (
            "model",
            "model_provider",
            "model_context_window",
            "model_max_output_tokens",
            "approval_policy",
        ):
            if k in prf:
                val = prf[k]
                if isinstance(val, (int, float)):
                    section_lines.append(f"{k} = {val}")
                elif isinstance(val, bool):
                    section_lines.append(f"{k} = {'true' if val else 'false'}")
                else:
                    section_lines.append(f"{k} = {json.dumps(val)}")
        if section_lines:
            lines.append("")
            lines.append(f"[profiles.{name}]")
            lines.extend(section_lines)

    out = "\n".join(lines).strip() + "\n"
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def to_json(cfg: Dict) -> str:
    """Serialize ``cfg`` to a pretty-printed JSON string."""
    return json.dumps(cfg, indent=2)


def to_yaml(cfg: Dict) -> str:
    """Tiny YAML emitter to avoid external deps."""

    def dump(obj, indent=0):
        sp = "  " * indent
        if isinstance(obj, dict):
            out: List[str] = []
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    out.append(f"{sp}{k}:")
                    out.append(dump(v, indent + 1))
                else:
                    out.append(f"{sp}{k}: {json.dumps(v)}")
            return "".join(out)
        elif isinstance(obj, list):
            out: List[str] = []
            for v in obj:
                if isinstance(v, (dict, list)):
                    out.append(f"{sp}-")
                    out.append(dump(v, indent + 1))
                else:
                    out.append(f"{sp}- {json.dumps(v)}")
            return "".join(out)
        else:
            return f"{sp}{json.dumps(obj)}"

    return dump(cfg) + ""


__all__ = [
    "build_config_dict",
    "to_toml",
    "to_json",
    "to_yaml",
]
