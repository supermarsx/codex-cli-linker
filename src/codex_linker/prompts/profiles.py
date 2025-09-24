from __future__ import annotations

import sys
import getpass
from typing import List, Dict, Any

from ..spec import PROVIDER_LABELS, DEFAULT_OPENAI, DEFAULT_LMSTUDIO, DEFAULT_OLLAMA, DEFAULT_ANTHROPIC, DEFAULT_OPENROUTER, DEFAULT_GROQ, DEFAULT_MISTRAL, DEFAULT_DEEPSEEK, DEFAULT_COHERE, DEFAULT_BASETEN, DEFAULT_LLAMACPP, DEFAULT_KOBOLDCPP, DEFAULT_JAN, DEFAULT_ANYTHINGLLM
from ..detect import list_models, try_auto_context_window
from ..ui import c, BOLD, CYAN, GRAY, info, warn, ok, err
from ..io_safe import AUTH_JSON, write_auth_json_merge
from .input_utils import (prompt_choice, _safe_input, _is_null_input, fmt)
from .profiles_edit import _edit_profile_entry_interactive


def manage_profiles_interactive(args) -> None:
    args.profile_overrides = getattr(args, "profile_overrides", {}) or {}
    while True:
        print()
        print(c(fmt("Profiles 👤:"), BOLD))
        names: List[str] = []
        main_name = args.profile or "<auto>"
        names.append(main_name)
        for k in (args.profile_overrides or {}).keys():
            if k not in names:
                names.append(k)
        for n in names:
            print(c(f" - {n}", CYAN))
        i = prompt_choice(
            "Choose",
            [
                "Add profile ➕",
                "Edit profile ✏️",
                "Remove profile 🗑️",
                "Back to main menu 🏠",
            ],
        )
        if i == 0:
            name = _safe_input("Profile name: ").strip()
            if not name:
                continue
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
                return
            if src == 0:
                names2: List[str] = []
                if getattr(args, "provider", None):
                    names2.append(args.provider)
                for k in (getattr(args, "provider_overrides", {}) or {}).keys():
                    if k not in names2:
                        names2.append(k)
                for p in (getattr(args, "providers_list", []) or []):
                    if p not in names2:
                        names2.append(p)
                if not names2:
                    warn("No providers configured yet; use presets or manual entry.")
                    continue
                pi = prompt_choice("Use which provider?", names2)
                provider = names2[pi]
            elif src == 1:
                base_presets = sorted(
                    [(pid, lbl) for pid, lbl in PROVIDER_LABELS.items()],
                    key=lambda x: x[1].lower(),
                )
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
                if chosen == "openai:api":
                    provider = "openai"
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
                try:
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
                        if provider != "azure":
                            args.base_url = default_base_by_provider.get(provider, getattr(args, "base_url", ""))
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
                provider = _safe_input("Provider id (e.g., lmstudio, ollama, openai): ").strip() or (args.provider or "")
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
                    print(f"  Context window: {int(ov.get('model_context_window') or 0)}")
                    print(f"  Max output tokens: {int(ov.get('model_max_output_tokens') or 0)}")
                    print(f"  Approval policy: {ov.get('approval_policy','')}")
                    print(f"  File opener: {ov.get('file_opener','')}")
                    print(f"  Reasoning effort: {ov.get('model_reasoning_effort','')}")
                    print(f"  Reasoning summary: {ov.get('model_reasoning_summary','')}")
                    print(f"  Verbosity: {ov.get('model_verbosity','')}")
                    print(f"  Disable response storage: {str(ov.get('disable_response_storage', False)).lower()}")
                    print(f"  Sandbox mode: {ov.get('sandbox_mode','')}")
                    print(f"  ChatGPT base URL: {ov.get('chatgpt_base_url','')}")
                    print(f"  Preferred auth method: {ov.get('preferred_auth_method','')}")
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
                from .input_utils import prompt_yes_no

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



def _default_env_key_for_profile(provider: str, profile: str) -> str:
    prov = (provider or 'custom').upper().replace('-', '_')
    prof = (profile or 'default').upper().replace('-', '_')
    return f"{prov}_{prof}_API_KEY"
