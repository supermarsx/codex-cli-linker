#!/usr/bin/env python3
"""Compatibility shim that re-exports the CLI implementation."""
from pathlib import Path
import sys

# Ensure local src/ is importable when running from repo without install
_here = Path(__file__).resolve().parent
_src = _here / "src"
if str(_src) not in sys.path and _src.exists():  # pragma: no cover
    sys.path.insert(0, str(_src))

from codex_linker.impl import *  # type: ignore  # noqa: F401,F403
from codex_linker.impl import main as _entry_main, warn as _warn  # type: ignore


if __name__ == "__main__":  # pragma: no cover
    try:
        _entry_main()
    except KeyboardInterrupt:
        print()
        try:
            _warn("Aborted by user.")
        except Exception:
            pass
