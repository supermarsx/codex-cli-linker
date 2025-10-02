from __future__ import annotations

import sys
from ..detect import list_models, try_auto_context_window
from ..ui import c, BOLD, GRAY, warn, ok, err, clear_screen
from .input_utils import prompt_choice, _safe_input, _is_null_input, fmt


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
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        print()
        print(c(f"Edit profile [{name}]", BOLD))
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
        df_supports_summ = bool(
            getattr(args, "model_supports_reasoning_summaries", False)
        )
        df_hist_p = "none" if getattr(args, "no_history", False) else "save-all"
        df_hist_b = getattr(args, "history_max_bytes", 0) or 0
        df_tools_ws = bool(getattr(args, "tools_web_search", False))
        items = [
            ("Provider", ov.get("provider") or "", f"Default: {args.provider or ''}"),
            (
                "Model",
                ov.get("model") or "",
                f"Default: {getattr(args, 'model', '') or 'gpt-5'}",
            ),
            ("Context window", str(ov.get("model_context_window") or 0), "Default: 0"),
            (
                "Max output tokens",
                str(ov.get("model_max_output_tokens") or 0),
                "Default: 0",
            ),
            (
                "Approval policy",
                ov.get("approval_policy") or df_approval,
                f"Default: {df_approval}",
            ),
            ("File opener", ov.get("file_opener") or "", f"Default: {df_file_opener}"),
            (
                "Reasoning effort",
                ov.get("model_reasoning_effort") or "",
                f"Default: {df_reason_effort or 'minimal/low'}",
            ),
            (
                "Reasoning summary",
                ov.get("model_reasoning_summary") or "",
                f"Default: {df_reason_summary or 'auto'}",
            ),
            (
                "Verbosity",
                ov.get("model_verbosity") or "",
                f"Default: {df_verbosity or 'medium'}",
            ),
            (
                "Disable response storage",
                "true" if ov.get("disable_response_storage") else "false",
                f"Default: {'true' if df_disable_resp else 'false'}",
            ),
            ("Sandbox mode", ov.get("sandbox_mode") or "", f"Default: {df_sandbox}"),
            (
                "ChatGPT base URL",
                ov.get("chatgpt_base_url") or "",
                f"Default: {df_chatgpt_base or '<empty>'}",
            ),
            (
                "Preferred auth method",
                ov.get("preferred_auth_method") or "",
                f"Default: {df_auth_method or 'apikey'}",
            ),
            (
                "Hide agent reasoning",
                "true" if ov.get("hide_agent_reasoning") else "false",
                f"Default: {'true' if df_hide else 'false'}",
            ),
            (
                "Show raw agent reasoning",
                "true" if ov.get("show_raw_agent_reasoning") else "false",
                f"Default: {'true' if df_show_raw else 'false'}",
            ),
            (
                "Model supports reasoning summaries",
                "true" if ov.get("model_supports_reasoning_summaries") else "false",
                f"Default: {'true' if df_supports_summ else 'false'}",
            ),
            (
                "History persistence",
                (ov.get("history_persistence") or df_hist_p),
                f"Default: {df_hist_p}",
            ),
            (
                "History max bytes",
                str(
                    ov.get("history_max_bytes")
                    if ov.get("history_max_bytes") is not None
                    else df_hist_b
                ),
                f"Default: {df_hist_b}",
            ),
            (
                "Tools: web_search",
                "true" if ov.get("tools_web_search") else "false",
                f"Default: {'true' if df_tools_ws else 'false'}",
            ),
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
                fmt("🏠 Back to main menu"),
            ],
        )
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                m = prompt_choice(
                    "Set provider", ["Choose from existing providers", "Enter manually"]
                )
                if m == 0:
                    names: list[str] = []
                    if getattr(args, "provider", None):
                        names.append(args.provider)
                    for k in (getattr(args, "provider_overrides", {}) or {}).keys():
                        if k not in names:
                            names.append(k)
                    for p in getattr(args, "providers_list", []) or []:
                        if p not in names:
                            names.append(p)
                    if not names:
                        warn("No providers configured; enter manually.")
                        ov["provider"] = (
                            _safe_input("Provider: ").strip()
                            or ov.get("provider")
                            or ""
                        )
                    else:
                        pi = prompt_choice("Use which provider?", names)
                        ov["provider"] = names[pi]
                else:
                    ov["provider"] = (
                        _safe_input("Provider: ").strip() or ov.get("provider") or ""
                    )
            elif idx == 1:
                mode = prompt_choice(
                    "Set model", ["Enter manually", "Auto-detect from server"]
                )
                if mode == 0:
                    ov["model"] = (
                        _safe_input("Model: ").strip() or ov.get("model") or ""
                    )
                else:
                    # Use provider-specific base_url when available, else sensible default, else prompt
                    pid = (ov.get("provider") or getattr(args, "provider", "")).strip()
                    base = ""
                    try:
                        pov = getattr(args, "provider_overrides", {}) or {}
                        if pid and pid in pov:
                            base = (pov.get(pid, {}).get("base_url") or "").strip()
                    except Exception:
                        base = ""
                    if not base:
                        # Fallback default base per known provider ids
                        mapping = {
                            "lmstudio": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_LMSTUDIO"]
                                ),
                                "DEFAULT_LMSTUDIO",
                                "",
                            ),
                            "ollama": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_OLLAMA"]
                                ),
                                "DEFAULT_OLLAMA",
                                "",
                            ),
                            "vllm": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_VLLM"]
                                ),
                                "DEFAULT_VLLM",
                                "",
                            ),
                            "tgwui": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_TGWUI"]
                                ),
                                "DEFAULT_TGWUI",
                                "",
                            ),
                            "tgi": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_TGI_8080"]
                                ),
                                "DEFAULT_TGI_8080",
                                "",
                            ),
                            "openrouter": getattr(
                                __import__(
                                    "codex_linker.spec",
                                    fromlist=["DEFAULT_OPENROUTER_LOCAL"],
                                ),
                                "DEFAULT_OPENROUTER_LOCAL",
                                "",
                            ),
                            "openrouter-remote": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_OPENROUTER"]
                                ),
                                "DEFAULT_OPENROUTER",
                                "",
                            ),
                            "openai": getattr(
                                __import__(
                                    "codex_linker.spec", fromlist=["DEFAULT_OPENAI"]
                                ),
                                "DEFAULT_OPENAI",
                                "",
                            ),
                        }
                        base = mapping.get(
                            pid, (getattr(args, "base_url", "") or "").strip()
                        )
                    if not base:
                        base = _safe_input(
                            "Base URL for model list (e.g., http://localhost:1234/v1): "
                        ).strip()
                    try:
                        mod = sys.modules.get("codex_cli_linker")
                        lm = getattr(mod, "list_models", list_models)
                        models = lm(base)
                        if models:
                            print(c("Available models:", BOLD))
                            # Provide models plus a custom entry
                            options = list(models) + ["✍️ Enter custom model"]
                            pick = prompt_choice("Choose model", options)
                            if pick == len(options) - 1:
                                custom = _safe_input("Model: ").strip()
                                if custom:
                                    ov["model"] = custom
                            else:
                                ov["model"] = models[pick]
                        else:
                            warn("No models returned; leaving model empty.")
                    except Exception as e:
                        err(f"Model detection failed: {e}")
            elif idx == 2:
                mode = prompt_choice(
                    "Set context window",
                    [
                        "Enter value",
                        "Auto-detect for current model",
                        "Skip (no change)",
                    ],
                )
                if mode == 0:
                    s2 = _safe_input("Context window (blank to skip): ").strip()
                    if s2:
                        try:
                            ov["model_context_window"] = int(s2)
                        except Exception:
                            pass
                else:
                    if mode == 2:
                        pass
                    else:
                        base = (getattr(args, "base_url", "") or "").strip()
                        if not base:
                            base = _safe_input(
                                "Base URL for detection (e.g., http://localhost:1234/v1): "
                            ).strip()
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
                            tacw = getattr(
                                sys.modules.get("codex_cli_linker"),
                                "try_auto_context_window",
                                try_auto_context_window,
                            )
                            cw = tacw(base, model)
                            if cw > 0:
                                ov["model_context_window"] = cw
                                ok(f"Detected context window: {cw} tokens")
                            else:
                                warn(
                                    "Could not detect context window; leaving unchanged."
                                )
                        except Exception as e:
                            err(f"Context window detection failed: {e}")
            elif idx == 3:
                s2 = _safe_input(
                    "Max output tokens (blank to skip, 'null' to clear): "
                ).strip()
                if s2:
                    if _is_null_input(s2):
                        ov["model_max_output_tokens"] = ""
                    else:
                        try:
                            ov["model_max_output_tokens"] = int(s2)
                        except Exception:
                            pass
            elif idx == 4:
                i2 = prompt_choice(
                    "Approval policy",
                    [
                        "untrusted",
                        "on-failure",
                        "on-request",
                        "never",
                        "Skip (no change)",
                        "Set to null",
                    ],
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
                    [
                        "vscode",
                        "vscode-insiders",
                        "windsurf",
                        "cursor",
                        "none",
                        "Skip (no change)",
                        "Set to null",
                    ],
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
                i2 = prompt_choice(
                    "Reasoning effort",
                    [
                        "minimal",
                        "low",
                        "medium",
                        "high",
                        "auto",
                        "Skip (no change)",
                        "Set to null",
                    ],
                )
                if i2 < 5:
                    ov["model_reasoning_effort"] = [
                        "minimal",
                        "low",
                        "medium",
                        "high",
                        "auto",
                    ][i2]
                elif i2 == 6:
                    ov["model_reasoning_effort"] = ""
            elif idx == 7:
                i2 = prompt_choice(
                    "Reasoning summary",
                    [
                        "auto",
                        "concise",
                        "detailed",
                        "none",
                        "Skip (no change)",
                        "Set to null",
                    ],
                )
                if i2 < 4:
                    ov["model_reasoning_summary"] = [
                        "auto",
                        "concise",
                        "detailed",
                        "none",
                    ][i2]
                elif i2 == 5:
                    ov["model_reasoning_summary"] = ""
            elif idx == 8:
                i2 = prompt_choice(
                    "Verbosity",
                    ["low", "medium", "high", "Skip (no change)", "Set to null"],
                )
                if i2 < 3:
                    ov["model_verbosity"] = ["low", "medium", "high"][i2]
                elif i2 == 4:
                    ov["model_verbosity"] = ""
            elif idx == 9:
                i2 = prompt_choice(
                    "Disable response storage",
                    ["true", "false", "Skip (no change)", "Set to null"],
                )
                if i2 < 2:
                    ov["disable_response_storage"] = True if i2 == 0 else False
                elif i2 == 3:
                    ov["disable_response_storage"] = ""
            elif idx == 10:
                i2 = prompt_choice(
                    "Sandbox mode",
                    [
                        "read-only",
                        "workspace-write",
                        "danger-full-access",
                        "Skip (no change)",
                        "Set to null",
                    ],
                )
                if i2 < 3:
                    ov["sandbox_mode"] = [
                        "read-only",
                        "workspace-write",
                        "danger-full-access",
                    ][i2]
                elif i2 == 4:
                    ov["sandbox_mode"] = ""
            elif idx == 11:
                s2 = _safe_input(
                    "ChatGPT base URL (blank to skip, 'null' to clear): "
                ).strip()
                if s2:
                    if _is_null_input(s2):
                        ov["chatgpt_base_url"] = ""
                    else:
                        ov["chatgpt_base_url"] = s2
            elif idx == 12:
                i2 = prompt_choice(
                    "Preferred auth method",
                    ["apikey", "chatgpt", "Skip (no change)", "Set to null"],
                )
                if i2 < 2:
                    ov["preferred_auth_method"] = ["apikey", "chatgpt"][i2]
                elif i2 == 3:
                    ov["preferred_auth_method"] = ""
            elif idx == 13:
                i2 = prompt_choice(
                    "Hide agent reasoning", ["true", "false", "Set to null"]
                )
                if i2 == 2:
                    ov["hide_agent_reasoning"] = ""
                else:
                    ov["hide_agent_reasoning"] = True if i2 == 0 else False
            elif idx == 14:
                i2 = prompt_choice(
                    "Show raw agent reasoning", ["true", "false", "Set to null"]
                )
                if i2 == 2:
                    ov["show_raw_agent_reasoning"] = ""
                else:
                    ov["show_raw_agent_reasoning"] = True if i2 == 0 else False
            elif idx == 15:
                i2 = prompt_choice(
                    "Model supports reasoning summaries",
                    ["true", "false", "Set to null"],
                )
                if i2 == 2:
                    ov["model_supports_reasoning_summaries"] = ""
                else:
                    ov["model_supports_reasoning_summaries"] = (
                        True if i2 == 0 else False
                    )
            elif idx == 16:
                i2 = prompt_choice(
                    "History persistence", ["save-all", "none", "Set to null"]
                )
                if i2 == 2:
                    ov["history_persistence"] = ""
                else:
                    ov["history_persistence"] = ["save-all", "none"][i2]
            elif idx == 17:
                s2 = _safe_input(
                    "History max bytes (blank to skip, 'null' to clear): "
                ).strip()
                if s2:
                    if _is_null_input(s2):
                        ov["history_max_bytes"] = ""
                    else:
                        try:
                            ov["history_max_bytes"] = int(s2)
                        except Exception:
                            pass
            elif idx == 18:
                i2 = prompt_choice("tools.web_search", ["true", "false", "Set to null"])
                if i2 == 2:
                    ov["tools_web_search"] = ""
                else:
                    ov["tools_web_search"] = True if i2 == 0 else False
        elif act == 1:
            ov["provider"] = (
                _safe_input("Provider: ").strip() or ov.get("provider") or ""
            )
            mode = prompt_choice(
                "Set model", ["Enter manually", "Auto-detect from server"]
            )
            if mode == 0:
                ov["model"] = _safe_input("Model: ").strip() or ov.get("model") or ""
            else:
                base = (getattr(args, "base_url", "") or "").strip()
                if not base:
                    base = _safe_input(
                        "Base URL for model list (e.g., http://localhost:1234/v1): "
                    ).strip()
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
            mode_cw = prompt_choice(
                "Set context window", ["Enter value", "Auto-detect for current model"]
            )
            if mode_cw == 0:
                try:
                    ov["model_context_window"] = int(
                        _safe_input("Context window: ").strip() or "0"
                    )
                except Exception:
                    pass
            else:
                base = (getattr(args, "base_url", "") or "").strip()
                if not base:
                    base = _safe_input(
                        "Base URL for detection (e.g., http://localhost:1234/v1): "
                    ).strip()
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
                    tacw = getattr(
                        sys.modules.get("codex_cli_linker"),
                        "try_auto_context_window",
                        try_auto_context_window,
                    )
                    cw = tacw(base, model)
                    if cw > 0:
                        ov["model_context_window"] = cw
                        ok(f"Detected context window: {cw} tokens")
                except Exception as e:
                    err(f"Context window detection failed: {e}")
            try:
                ov["model_max_output_tokens"] = int(
                    _safe_input("Max output tokens: ").strip() or "0"
                )
            except Exception:
                pass
            i2 = prompt_choice(
                "Approval policy", ["untrusted", "on-failure", "on-request", "never"]
            )
            ov["approval_policy"] = ["untrusted", "on-failure", "on-request", "never"][
                i2
            ]
        elif act == 2:
            args.profile_overrides[name] = ov
            ok("Saved.")
            return
        elif act == 4:
            raise KeyboardInterrupt
        else:
            return
