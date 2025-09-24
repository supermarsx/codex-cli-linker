from __future__ import annotations

from ..state import LinkerState
from ..ui import c, BOLD, info
from .input_utils import prompt_choice, fmt, set_emojis_enabled
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
        print()
        # Honor CLI toggle for emojis
        set_emojis_enabled(not getattr(args, "no_emojis", False))
        print(c(fmt("Interactive settings ⚙️:"), BOLD))
        try:
            hub = prompt_choice(
                "Start with",
                [
                    "Manage profiles 👤",
                    "Manage MCP servers 🧰",
                    "Manage providers 🔌",
                    "Global settings ⚙️",
                    "Actions… 🚀",
                    "Legacy pipeline (guided) 🧭",
                    "Quit (no write) ❌",
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
        if hub == 4:
            try:
                act = prompt_choice(
                    "Action",
                    [
                        "Write 💾",
                        "Overwrite + Write 📝",
                        "Write and launch (print cmd) 🚀",
                        "Back ⬅️",
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
        if hub == 5:
            return "legacy"
        if hub == 6:
            return "quit"
        # hub == 3: Global settings are handled in the old flow, keep loop
        continue
