from __future__ import annotations

from ..state import LinkerState
from ..ui import c, BOLD, info, ok, warn, clear_screen, banner
import time
import logging
from .input_utils import prompt_choice, fmt, set_emojis_enabled
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
    global _HUB_CTRL_C_COUNT
    _HUB_CTRL_C_COUNT += 1
    if _HUB_CTRL_C_COUNT >= 2:
        print()
        raise SystemExit(0)
    from ..ui import warn
    from .input_utils import fmt

    warn(fmt("Press Ctrl-C again to exit ⏹️  Returning to main menu… 🏠"))


def interactive_settings_editor(state: LinkerState, args) -> str:
    while True:
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        # Show banner as part of the hub unless suppressed
        if not getattr(args, "no_banner", False):
            try:
                banner()
            except Exception:
                pass
        print()
        # Honor CLI toggle for emojis
        set_emojis_enabled(not getattr(args, "no_emojis", False))
        print(c(fmt("Interactive settings ⚙️:"), BOLD))
        try:
            hub = prompt_choice(
                "Start with",
                [
                    fmt("👤 Manage profiles"),
                    fmt("🧰 Manage MCP servers"),
                    fmt("🔌 Manage providers"),
                    fmt("🪄 Add local LLMs automagically"),
                    fmt("⚙️ Global settings"),
                    fmt("🚀 Actions…"),
                    fmt("🧭 Guided pipeline"),
                    fmt("❌ Quit (no write)"),
                ],
            )
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
            profiles_added = 0
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
                    args.provider_overrides = getattr(args, "provider_overrides", {}) or {}
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
        if hub == 5:
            try:
                act = prompt_choice(
                    "Action",
                    [
                        fmt("💾 Write"),
                        fmt("📝 Overwrite + Write"),
                        fmt("🚀 Write and launch (print cmd)"),
                        fmt("Back 🔙"),
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
