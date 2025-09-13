#!/usr/bin/env python3
"""Compatibility shim that re-exports the CLI implementation."""
from pathlib import Path
import sys

# Ensure local src/ is importable when running from repo without install
_here = Path(__file__).resolve().parent
_src = _here / "src"
if str(_src) not in sys.path and _src.exists():  # pragma: no cover
    sys.path.insert(0, str(_src))

from codex_linker.impl import *  # type: ignore  # noqa: F401,F403,E402
from codex_linker.impl import main as _entry_main, warn as _warn  # type: ignore  # noqa: E402
from codex_linker import utils as _utils  # noqa: E402


def launch_codex(profile: str) -> int:  # noqa: D401
    """Wrapper that forwards to utils.launch_codex using this module's ensure."""
    return _utils.launch_codex(profile, ensure_codex_cli)


if __name__ == "__main__":  # pragma: no cover
    try:
        _entry_main()
    except KeyboardInterrupt:
        print()
        try:
            _warn("Aborted by user.")
        except Exception:
            pass
