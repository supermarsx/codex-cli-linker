from __future__ import annotations

"""Interactive settings hub.

The hub presents a single menu for common tasks (profiles, providers, MCP,
global settings, actions, and the guided pipeline). It owns banner display and
ensures the banner is shown at most once per session, avoiding duplicates on
startup.
"""

from ..state import LinkerState
from ..ui import c, BOLD, info, ok, warn, clear_screen, banner
import time
import logging
from .input_utils import prompt_choice, fmt, set_emojis_enabled, _safe_input
from .input_utils import _input_list_json
from ..spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_OPENROUTER_LOCAL,
    PROVIDER_LABELS,
)
from ..detect import list_models
from .profiles import manage_profiles_interactive
from .mcp import manage_mcp_servers_interactive
from .providers import manage_providers_interactive

_HUB_CTRL_C_COUNT = 0


def _handle_ctrlc_in_hub() -> None:
    """Convert the first Ctrl-C into a friendly message; exit on second."""
    global _HUB_CTRL_C_COUNT
    _HUB_CTRL_C_COUNT += 1
    if _HUB_CTRL_C_COUNT >= 2:
        print()
        raise SystemExit(0)
    from ..ui import warn
    from .input_utils import fmt

    warn(fmt("Press Ctrl-C again to exit ⏹️  Returning to main menu… 🏠"))


def interactive_settings_editor(state: LinkerState, args) -> str:
    """Run the interactive settings hub.

    Returns a short action string (e.g., ``"write"``) or terminates the loop
    by returning ``"quit"``. The caller decides how to handle the result.
    """
    while True:
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        # Honor CLI toggle for emojis
        set_emojis_enabled(not getattr(args, "no_emojis", False))
        # Show banner once (hub owns banner), unless suppressed or in continuous mode
        if (
            not getattr(args, "_hub_banner_shown", False)
            and not getattr(args, "no_banner", False)
            and not getattr(args, "continuous", False)
        ):
            try:
                banner()
            except Exception:
                pass
            setattr(args, "_hub_banner_shown", True)
        print()
        print(c(fmt("⚙️  Interactive settings:"), BOLD))
        try:
            hub = prompt_choice(
                "Start with",
                [
                    fmt("👤 Manage profiles"),
                    fmt("🧰 Manage MCP servers"),
                    fmt("🔌 Manage providers"),
                    fmt("🪄 Add local LLMs automagically"),
                    fmt("⚙️  Global settings"),
                    fmt("🚀 Actions…"),
                    fmt("🧭 Guided pipeline"),
                    fmt("❌ Quit (no write)"),
                ],
            )
            # Clear immediately after selection (not in continuous), before running action
            if not getattr(args, "continuous", False):
                try:
                    clear_screen()
                except Exception:
                    pass
        except KeyboardInterrupt:
            _handle_ctrlc_in_hub()
            continue
        if hub == 0:
            try:
                manage_profiles_interactive(args)
            except KeyboardInterrupt:
                continue
            continue
        if hub == 1:
            try:
                manage_mcp_servers_interactive(args)
            except KeyboardInterrupt:
                continue
            continue
        if hub == 2:
            try:
                manage_providers_interactive(args)
            except KeyboardInterrupt:
                continue
            continue
        if hub == 3:
            # Auto-detect local providers and add them with models
            candidates = [
                ("lmstudio", DEFAULT_LMSTUDIO),
                ("ollama", DEFAULT_OLLAMA),
                ("vllm", DEFAULT_VLLM),
                ("tgwui", DEFAULT_TGWUI),
                ("tgi", DEFAULT_TGI_8080),
                ("openrouter", DEFAULT_OPENROUTER_LOCAL),
            ]
            log = logging.getLogger(__name__)
            log.info("Auto-detect: probing local providers (hub)")
            added = 0
            for pid, base in candidates:
                try:
                    log.debug("Probing %s at %s", pid, base)
                    models = list_models(base)
                    if not models:
                        log.debug("No models for %s at %s", pid, base)
                        continue
                    log.debug("Found %d models for %s: %s", len(models), pid, models)
                    entry = {
                        "name": PROVIDER_LABELS.get(pid, pid.capitalize()),
                        "base_url": base,
                        "env_key": "",
                        "wire_api": "chat",
                    }
                    args.provider_overrides = (
                        getattr(args, "provider_overrides", {}) or {}
                    )
                    args.provider_overrides[pid] = entry
                    # Ensure provider listed
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
            # Brief pause before screen changes when not continuous
            if not getattr(args, "continuous", False):
                try:
                    time.sleep(1.0)
                except Exception:
                    pass
            continue
        if hub == 4:
            # Manage global settings interactively
            try:
                _manage_global_settings_interactive(args)
            except KeyboardInterrupt:
                pass
            # After returning, loop back to hub; no extra clear here
            continue
        if hub == 5:
            try:
                act = prompt_choice(
                    "Action",
                    [
                        fmt("💾 Write"),
                        fmt("📝 Overwrite + Write"),
                        fmt("🚀 Write and launch (print cmd)"),
                        fmt("🔙 Back"),
                    ],
                )
            except KeyboardInterrupt:
                continue
            if act == 0:
                return "write"
            if act == 1:
                return "overwrite"
            if act == 2:
                return "write_and_launch"
            continue
        if hub == 6:
            return "legacy"
        if hub == 7:
            return "quit"
        # hub == 3: Global settings are handled in the old flow, keep loop
        continue


def _manage_global_settings_interactive(args) -> None:
    while True:
        print()
        print(c(fmt("⚙️ Global settings"), BOLD))
        items = [
            ("Approval policy", getattr(args, "approval_policy", "")),
            ("Sandbox mode", getattr(args, "sandbox_mode", "")),
            (
                "Network access",
                "true" if getattr(args, "network_access", False) else "false",
            ),
            ("Writable roots (CSV)", getattr(args, "writable_roots", "") or ""),
            ("File opener", getattr(args, "file_opener", "")),
            ("Reasoning effort", getattr(args, "reasoning_effort", "")),
            ("Reasoning summary", getattr(args, "reasoning_summary", "")),
            ("Verbosity", getattr(args, "verbosity", "")),
            (
                "Hide agent reasoning",
                "true" if getattr(args, "hide_agent_reasoning", False) else "false",
            ),
            (
                "Show raw agent reasoning",
                "true" if getattr(args, "show_raw_agent_reasoning", False) else "false",
            ),
            (
                "Disable response storage",
                "true" if getattr(args, "disable_response_storage", False) else "false",
            ),
            ("History max bytes", str(getattr(args, "history_max_bytes", 0) or 0)),
            ("No history", "true" if getattr(args, "no_history", False) else "false"),
            (
                "tools.web_search",
                "true" if getattr(args, "tools_web_search", False) else "false",
            ),
            ("Wire API", getattr(args, "wire_api", "")),
            ("ChatGPT base URL", getattr(args, "chatgpt_base_url", "")),
            ("Azure api-version", getattr(args, "azure_api_version", "")),
            (
                "Project doc max bytes",
                str(getattr(args, "project_doc_max_bytes", 0) or 0),
            ),
            ("Notify (JSON array)", getattr(args, "notify", "") or ""),
        ]
        for i, (lbl, val) in enumerate(items, 1):
            print(f"  {i}. {lbl}: {val}")
        act = prompt_choice(
            "Action", [fmt("✏️ Edit field"), fmt("🏠 Back to main menu")]
        )
        # Clear immediately after selection when not continuous
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        if act == 1:
            return
        # Edit field
        s = _safe_input("Field number: ").strip()
        if not s.isdigit():
            continue
        idx = int(s) - 1
        if idx == 0:
            i2 = prompt_choice(
                "Approval policy", ["untrusted", "on-failure", "on-request", "never"]
            )
            args.approval_policy = ["untrusted", "on-failure", "on-request", "never"][
                i2
            ]
        elif idx == 1:
            i2 = prompt_choice(
                "Sandbox mode", ["read-only", "workspace-write", "danger-full-access"]
            )
            args.sandbox_mode = ["read-only", "workspace-write", "danger-full-access"][
                i2
            ]
        elif idx == 2:
            i2 = prompt_choice("Network access", ["true", "false"])
            args.network_access = True if i2 == 0 else False
        elif idx == 3:
            args.writable_roots = _safe_input("Writable roots CSV: ").strip()
        elif idx == 4:
            i2 = prompt_choice(
                "File opener",
                ["vscode", "vscode-insiders", "windsurf", "cursor", "none"],
            )
            args.file_opener = [
                "vscode",
                "vscode-insiders",
                "windsurf",
                "cursor",
                "none",
            ][i2]
        elif idx == 5:
            i2 = prompt_choice(
                "Reasoning effort", ["minimal", "low", "medium", "high", "auto"]
            )
            args.reasoning_effort = ["minimal", "low", "medium", "high", "auto"][i2]
        elif idx == 6:
            i2 = prompt_choice(
                "Reasoning summary", ["auto", "concise", "detailed", "none"]
            )
            args.reasoning_summary = ["auto", "concise", "detailed", "none"][i2]
        elif idx == 7:
            i2 = prompt_choice("Verbosity", ["low", "medium", "high"])
            args.verbosity = ["low", "medium", "high"][i2]
        elif idx == 8:
            i2 = prompt_choice("Hide agent reasoning", ["true", "false"])
            args.hide_agent_reasoning = True if i2 == 0 else False
        elif idx == 9:
            i2 = prompt_choice("Show raw agent reasoning", ["true", "false"])
            args.show_raw_agent_reasoning = True if i2 == 0 else False
        elif idx == 10:
            i2 = prompt_choice("Disable response storage", ["true", "false"])
            args.disable_response_storage = True if i2 == 0 else False
        elif idx == 11:
            try:
                args.history_max_bytes = int(
                    _safe_input("History max bytes: ").strip() or "0"
                )
            except Exception:
                pass
        elif idx == 12:
            i2 = prompt_choice("No history (persistence=none)", ["true", "false"])
            args.no_history = True if i2 == 0 else False
        elif idx == 13:
            i2 = prompt_choice("tools.web_search", ["true", "false"])
            args.tools_web_search = True if i2 == 0 else False
        elif idx == 14:
            i2 = prompt_choice("Wire API", ["chat", "responses"])
            args.wire_api = ["chat", "responses"][i2]
        elif idx == 15:
            args.chatgpt_base_url = _safe_input("ChatGPT base URL: ").strip()
        elif idx == 16:
            args.azure_api_version = _safe_input("Azure api-version: ").strip()
        elif idx == 17:
            try:
                args.project_doc_max_bytes = int(
                    _safe_input("Project doc max bytes: ").strip() or "0"
                )
            except Exception:
                pass
        elif idx == 18:
            arr = _input_list_json("Notify (JSON array)")
            try:
                import json as _json

                args.notify = _json.dumps(arr)
            except Exception:
                args.notify = ""
