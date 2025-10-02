from __future__ import annotations

from pathlib import Path

from ..config_utils import apply_saved_state
from ..logging_utils import log_event
from ..state import LinkerState


def select_state_path(args, home: Path, linker_json: Path) -> tuple[Path, bool]:
    """Determine the path to the state file, honoring workspace override and explicit path."""
    state_file_override = getattr(args, "state_file", None)
    workspace_state_path = Path.cwd() / ".codex-linker.json"
    use_workspace_state = getattr(args, "workspace_state", False)
    if state_file_override:
        state_path = Path(state_file_override)
    else:
        if not use_workspace_state and workspace_state_path.exists():
            use_workspace_state = True
        state_path = workspace_state_path if use_workspace_state else linker_json
    log_event(
        "state_path_selected",
        path=str(state_path),
        workspace=bool(use_workspace_state),
        override=bool(state_file_override),
    )
    return state_path, use_workspace_state


def load_and_apply_state(args, defaults, state_path: Path) -> LinkerState:
    """Load state from disk and apply saved defaults into args."""
    state = LinkerState.load(state_path)
    apply_saved_state(args, defaults, state)
    return state
