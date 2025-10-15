"""Console UI helpers (color, messages, and banner).

This module centralizes tiny, dependency‑free helpers for terminal output:
 - ANSI color/style codes gated by a conservative capability check
 - Convenience printers for info/ok/warn/error with consistent prefixes
 - A minimal banner and a best‑effort screen clear

Design goals:
 - No third‑party dependencies; safe to import anywhere
 - Never raise on capability checks or UI actions
 - Respect ``NO_COLOR`` and only emit ANSI when stdout is a TTY
"""

from __future__ import annotations
import os
import sys

# ANSI color/style codes (used only when supports_color() returns True)
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"
MAGENTA = "\033[35m"


def supports_color() -> bool:
    """Return True when ANSI colors are likely supported.

    Honors ``NO_COLOR`` to disable color globally and requires ``sys.stdout``
    to be a TTY. Any errors during detection result in ``False``.
    """
    try:
        if os.environ.get("NO_COLOR"):
            return False
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return False


def c(s: str, color: str) -> str:
    """Conditionally colorize a string.

    Parameters
    - ``s``: The text to wrap.
    - ``color``: An ANSI color/style escape prefix to apply.

    Returns the colorized string if supported, otherwise the original text.
    """
    return f"{color}{s}{RESET}" if supports_color() else s


def clear_screen() -> None:
    """Best‑effort terminal clear.

    Uses ``cls`` on Windows and ``clear`` elsewhere. Failures are ignored.
    """
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def banner() -> None:
    """Display the startup ASCII art banner in cyan.

    The interactive hub controls when this is shown (at most once per
    session). This function never raises.
    """
    art = r"""
                           _      _
          /               //     //         /
 _. __ __/ _  _., --- _. // o   // o ____  /_  _  __
(__(_)(_/_</_/ /\_   (__</_<_  </_<_/ / <_/ <_</_/ (_


"""
    print(c(art, CYAN))


def info(msg: str) -> None:
    """Print an informational message prefixed with "ℹ"."""
    print(c("ℹ ", BLUE) + msg)


def ok(msg: str) -> None:
    """Print a success message prefixed with "✓"."""
    print(c("✓ ", GREEN) + msg)


def warn(msg: str) -> None:
    """Print a warning message prefixed with "!"."""
    print(c("! ", YELLOW) + msg)


def err(msg: str) -> None:
    """Print an error message prefixed with "✗"."""
    print(c("✗ ", RED) + msg)


__all__ = [
    "supports_color",
    "c",
    "clear_screen",
    "banner",
    "info",
    "ok",
    "warn",
    "err",
    "RESET",
    "BOLD",
    "DIM",
    "RED",
    "GREEN",
    "YELLOW",
    "BLUE",
    "CYAN",
    "GRAY",
    "MAGENTA",
]
