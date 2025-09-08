#!/usr/bin/env python3
"""
Compatibility shim that re-exports the CLI implementation now housed in
the package under src/codex_linker/impl.py. Tests import this file directly.
"""
from pathlib import Path
import sys

# Ensure local src/ is importable when running from repo without install
_here = Path(__file__).resolve().parent
_src = _here / "src"
if str(_src) not in sys.path and _src.exists():  # pragma: no cover
    sys.path.insert(0, str(_src))

_impl_pkg = _src / "codex_linker" / "impl.py"
if _impl_pkg.exists():  # pragma: no cover
    code = _impl_pkg.read_text(encoding="utf-8")
    exec(compile(code, str(_impl_pkg), "exec"), globals(), globals())
else:
    # Fallback to installed package import
    from codex_linker.impl import *  # type: ignore  # noqa: E402,F401,F403
    from codex_linker.impl import main as _entry_main, warn as _warn  # type: ignore  # noqa: E402


if __name__ == "__main__":  # pragma: no cover
    try:
        # _entry_main exists only in fallback branch; otherwise 'main' now points to impl's main via exec
        (_entry_main if "_entry_main" in globals() else globals().get("main"))()
    except KeyboardInterrupt:
        print()
        try:
            (_warn if "_entry_main" in globals() else globals().get("warn"))(
                "Aborted by user."
            )
        except Exception:
            pass
