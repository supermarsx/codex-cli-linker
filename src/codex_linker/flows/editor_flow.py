from __future__ import annotations

"""Interactive editor (hub) flow.

Encapsulates the optional interactive hub that can:
- Toggle overwrite mode
- Request a direct write/launch ("fast write")
- Defer to the legacy guided pipeline
- Or skip entirely when not applicable
"""

from ..prompts import (
    interactive_settings_editor,
    manage_profiles_interactive,
    manage_mcp_servers_interactive,
)
from ..ui import info, err


def maybe_run_interactive_editor(state, args) -> str | None:
    """Optionally invoke the interactive editor/hub and handle its actions.

    Returns the action string or None if editor was not triggered. May set
    args._fast_write when the editor requests a direct write.
    """
    if getattr(args, "full_auto", False):
        return None
    trigger_editor = bool(getattr(args, "_no_args", False))
    trigger_editor = trigger_editor or getattr(args, "manage_profiles", False) or getattr(args, "manage_mcp", False)
    if not trigger_editor:
        return None

    action = interactive_settings_editor(state, args)
    if action == "quit":
        info("Aborted without writing.")
        raise SystemExit(0)
    if action == "overwrite":
        args.overwrite_profile = True
    if action in ("write", "write_and_launch"):
        setattr(args, "_fast_write", True)
    if action == "legacy":
        try:
            from ..guided_pipeline import run_guided_pipeline

            run_guided_pipeline(state, args)
            if getattr(args, "_guided_abort", False):
                info("Aborted without writing.")
                raise SystemExit(0)
        except Exception as e:
            err(str(e))
            raise SystemExit(2)
    return action


def maybe_post_editor_management(args) -> None:
    """Run optional legacy manage flows when requested after the editor."""
    if getattr(args, "full_auto", False):
        return
    # Mark that the editor managed knobs; keep legacy extras minimal
    args._ran_editor = True
    if getattr(args, "manage_profiles", False):
        manage_profiles_interactive(args)
    if getattr(args, "manage_mcp", False):
        manage_mcp_servers_interactive(args)
