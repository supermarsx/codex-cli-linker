"""Context window detection flow.

Contains a single helper that attempts to determine the model's context
window by querying the server's ``/models`` metadata, unless the value is
already provided or we are in a fast-write path.
"""

from __future__ import annotations

import sys
from ..detect import try_auto_context_window
from ..ui import ok, warn


def maybe_detect_context_window(args, state) -> None:
    """Auto-detect context window size unless provided or in fast-write mode.

    On success updates ``args.model_context_window`` and prints a short note.
    Failures are treated as informational only.
    """
    if (args.model_context_window or 0) > 0 or getattr(args, "_fast_write", False):
        return
    try:
        tacw = getattr(
            sys.modules.get("codex_cli_linker"),
            "try_auto_context_window",
            try_auto_context_window,
        )
        cw = tacw(state.base_url, state.model)
        if cw > 0:
            ok(f"Detected context window: {cw} tokens")
            args.model_context_window = cw
        else:
            warn("Could not detect context window; leaving as 0.")
    except Exception as _e:
        warn(f"Context window detection failed: {_e}")
