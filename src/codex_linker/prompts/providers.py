from __future__ import annotations

import getpass
from typing import List, Dict, Any

from ..spec import (
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
    PROVIDER_LABELS,
)
from ..ui import c, BOLD, CYAN, GRAY, ok, info, warn, err, clear_screen
import time
import logging
from ..detect import list_models
from ..io_safe import AUTH_JSON, write_auth_json_merge
from .input_utils import prompt_choice, _safe_input, _is_null_input, _parse_brace_kv, fmt


def _default_base_for_provider_id(pid: str) -> str:
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
    return mapping.get(pid, "")


def manage_providers_interactive(args) -> None:
    if not hasattr(args, "providers_list") or args.providers_list is None:
        args.providers_list = []
    if not hasattr(args, "provider_overrides") or args.provider_overrides is None:
        args.provider_overrides = {}
    while True:
        print()
        print(c(fmt("Providers 🔌:"), BOLD))
        names: List[str] = []
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
                fmt("🪄 Add providers automagically"),
                "➕ Add provider",
                "✏️ Edit provider",
                "🗑️ Remove provider",
                "✅ Done",
            ],
        )
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        if choice == 0:
            # Auto-detect local OpenAI-compatible providers and add them with available models
            candidates = [
                ("lmstudio", DEFAULT_LMSTUDIO),
                ("ollama", DEFAULT_OLLAMA),
                ("vllm", DEFAULT_VLLM),
                ("tgwui", DEFAULT_TGWUI),
                ("tgi", DEFAULT_TGI_8080),
                ("openrouter", DEFAULT_OPENROUTER_LOCAL),
            ]
            log = logging.getLogger(__name__)
            log.info("Auto-detect: probing local providers (providers menu)")
            added = 0
            for pid, base in candidates:
                try:
                    log.debug("Probing %s at %s", pid, base)
                    models = list_models(base)
                    if not models:
                        log.debug("No models for %s at %s", pid, base)
                        continue
                    log.debug("Found %d models for %s: %s", len(models), pid, models)
                    entry: Dict[str, Any] = {
                        "name": PROVIDER_LABELS.get(pid, pid.capitalize()),
                        "base_url": base,
                        "env_key": "",  # local engines generally don't need API keys
                        "wire_api": "chat",
                    }
                    args.provider_overrides = getattr(args, "provider_overrides", {}) or {}
                    args.provider_overrides[pid] = entry
                    # Track provider id list
                    plist = set(getattr(args, "providers_list", []) or [])
                    plist.add(pid)
                    args.providers_list = list(plist)
                    ok(f"Detected {pid} at {base}")
                    added += 1
                except Exception as e:
                    log.debug("Error probing %s at %s: %s", pid, base, e, exc_info=True)
                    warn(f"Skip {pid}: {e}")
            if added == 0:
                info("No local providers detected.")
            else:
                ok(f"Added {added} local provider(s).")
            if not getattr(args, "continuous", False):
                try:
                    time.sleep(1.0)
                except Exception:
                    pass
            continue
        if choice == 1:
            add_mode = prompt_choice("Add provider via", ["🎛️ Choose preset", "✍️ Enter custom"])
            if add_mode == 0:
                preset_ids = sorted(PROVIDER_LABELS.keys(), key=lambda k: PROVIDER_LABELS[k].lower())
                labels = []
                for pid0 in preset_ids:
                    default_base = _default_base_for_provider_id(pid0)
                    label = f"{PROVIDER_LABELS[pid0]} ({pid0})"
                    if default_base:
                        label += f"  [{default_base}]"
                    labels.append(label)
                labels.append(fmt("🏠 Back to main menu"))
                sel = prompt_choice("🎛️ Preset", labels)
                if sel == len(labels) - 1:
                    return
                chosen_pid = preset_ids[sel]
                default_pid = chosen_pid
                pid = _safe_input(f"Provider id [{default_pid}]: ").strip() or default_pid
                default_name = PROVIDER_LABELS.get(chosen_pid, chosen_pid.capitalize())
                print(c("Display name — shown in tools and UIs.", GRAY))
                pname = _safe_input(f"Display name [{default_name}]: ").strip() or default_name
                if chosen_pid == "azure":
                    resource = _safe_input("Azure resource name (e.g., myres): ").strip()
                    print(c("Azure path — typically 'openai'.", GRAY))
                    path = _safe_input("Path (e.g., openai) [openai]: ").strip() or "openai"
                    base = f"https://{resource}.openai.azure.com/{path}" if resource else ""
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
            default_env = f"{pid.upper().replace('-', '_')}_API_KEY"
            print(c("Env key — name of environment variable that holds the API key.", GRAY))
            envk = _safe_input(f"Env key name [{default_env}]: ").strip() or default_env
            try:
                secret = getpass.getpass(f"Enter API key for {pid} (env {envk}) [blank to skip]: ").strip()
            except Exception:
                secret = _safe_input(f"Enter API key for {pid} (env {envk}) [blank to skip]: ").strip()
            if secret:
                try:
                    write_auth_json_merge(AUTH_JSON, {envk: secret})
                    ok(f"Updated {AUTH_JSON} with {envk}")
                    warn("Never commit this file; it contains a secret.")
                except Exception as e:
                    err(f"Could not update {AUTH_JSON}: {e}")
            override_entry: Dict[str, Any] = {"name": pname, "base_url": base, "env_key": envk}
            default_wire = "responses" if ((add_mode == 0 and chosen_pid == "azure") or pid == "azure") else "chat"
            print(c("Wire API — choose 'chat' (Chat Completions) or 'responses' (Responses API).", GRAY))
            wi = prompt_choice("Wire API", ["chat", "responses", "Skip (use default)"])
            if wi < 2:
                override_entry["wire_api"] = ["chat", "responses"][wi]
            qpi = {}
            if (add_mode == 0 and 'apiver' in locals() and apiver):
                qpi = {"api-version": apiver}
            print(c("Query params — URL query parameters (e.g., api-version for Azure).", GRAY))
            qp_mode = prompt_choice("Query params", ["Keep defaults", "Edit ({key=\"value\",...})"])
            if qp_mode == 1:
                raw = _safe_input("Query params object (e.g., {api-version=\"2025-04-01-preview\"}): ").strip()
                if raw:
                    qpi = _parse_brace_kv(raw)
            if qpi:
                override_entry["query_params"] = qpi
            print(c("HTTP headers — add static or env-sourced headers to each request.", GRAY))
            hdr_mode = prompt_choice("HTTP headers", ["None", "Preset: Azure api-key", "Preset: Anthropic x-api-key", "Preset: Authorization from env", "Custom (CSV KEY=VAL)"])
            http_headers: Dict[str, str] = {}
            env_http_headers: Dict[str, str] = {}
            if hdr_mode == 1:
                env_http_headers = {"api-key": envk}
            elif hdr_mode == 2:
                env_http_headers = {"x-api-key": envk}
            elif hdr_mode == 3:
                env_http_headers = {"Authorization": envk}
            elif hdr_mode == 4:
                from .input_utils import _input_env_kv

                http_headers = _input_env_kv("HTTP headers CSV (KEY=VAL,...): ", {})
                env_http_headers = _input_env_kv("Env headers CSV (KEY=ENV,...): ", {})
            if http_headers:
                override_entry["http_headers"] = http_headers
            if env_http_headers:
                override_entry["env_http_headers"] = env_http_headers
            try:
                rr = _safe_input(f"Request max retries [{getattr(args, 'request_max_retries', 4)}]: ").strip()
                if rr:
                    override_entry["request_max_retries"] = int(rr)
            except Exception:
                pass
            try:
                sr = _safe_input(f"Stream max retries [{getattr(args, 'stream_max_retries', 10)}]: ").strip()
                if sr:
                    override_entry["stream_max_retries"] = int(sr)
            except Exception:
                pass
            try:
                idle = _safe_input(f"Stream idle timeout ms [{getattr(args, 'stream_idle_timeout_ms', 300000)}]: ").strip()
                if idle:
                    override_entry["stream_idle_timeout_ms"] = int(idle)
            except Exception:
                pass
            args.provider_overrides[pid] = override_entry
            if pid not in args.providers_list and pid != getattr(args, "provider", None):
                args.providers_list.append(pid)
            ok(f"Saved provider '{pid}'")
        elif choice == 2:
            if not names:
                warn("No providers to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            pid = names[idx]
            while True:
                ov = dict((args.provider_overrides or {}).get(pid) or {})
                print()
                print(c(f"Edit provider [{pid}]", BOLD))
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
                        "✏️ Edit field",
                        "🏷️ Rename provider id",
                        "💾 Save",
                        "❎ Cancel",
                        fmt("🏠 Back to main menu"),
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
                        wi = prompt_choice("Wire API", ["chat", "responses", "Skip (no change)", "Set to null"])
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
                                env1: Dict[str, str] = {}
                                for pair in raw.split(','):
                                    if '=' in pair:
                                        k, v = pair.split('=', 1)
                                        if k.strip():
                                            env1[k.strip()] = v.strip()
                                ov["http_headers"] = env1
                    elif fi == 7:
                        raw = _safe_input("Env headers CSV (KEY=ENV,...) (blank=skip, 'null'=clear): ").strip()
                        if raw:
                            if _is_null_input(raw):
                                ov["env_http_headers"] = {}
                            else:
                                env2: Dict[str, str] = {}
                                for pair in raw.split(','):
                                    if '=' in pair:
                                        k, v = pair.split('=', 1)
                                        if k.strip():
                                            env2[k.strip()] = v.strip()
                                ov["env_http_headers"] = env2
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
                    return
                else:
                    break
        elif choice == 3:
            if not names:
                warn("No providers to remove.")
                continue
            idx = prompt_choice("Remove which?", names)
            pid = names[idx]
            if pid == getattr(args, "provider", None):
                warn("Won't remove the current active provider; change provider first.")
                continue
            from .input_utils import prompt_yes_no

            if prompt_yes_no(f"Remove provider '{pid}'?", default=False):
                (args.provider_overrides or {}).pop(pid, None)
                if pid in (args.providers_list or []):
                    args.providers_list = [p for p in args.providers_list if p != pid]
                info(f"Removed provider: {pid}")
            else:
                info("Removal cancelled.")
        else:
            break
