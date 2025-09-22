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
    """Return True if the terminal likely supports ANSI colors."""
    try:
        if os.environ.get("NO_COLOR"):
            return False
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return False


def c(s: str, color: str) -> str:
    """Apply a color code when the terminal supports it."""
    return f"{color}{s}{RESET}" if supports_color() else s


def clear_screen() -> None:
    """Best effort attempt to clear the terminal."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def banner() -> None:
    """Display the startup ASCII art banner."""
    art = r"""
                           _      _
          /               //     //         /
 _. __ __/ _  _., --- _. // o   // o ____  /_  _  __
(__(_)(_/_</_/ /\_   (__</_<_  </_<_/ / <_/ <_</_/ (_


"""
    print(c(art, CYAN))


def info(msg: str) -> None:
    """Print an informational message prefixed with ℹ."""
    print(c("ℹ ", BLUE) + msg)


def ok(msg: str) -> None:
    """Print a success message prefixed with a check mark."""
    print(c("✓ ", GREEN) + msg)


def warn(msg: str) -> None:
    """Print a warning message prefixed with an exclamation mark."""
    print(c("! ", YELLOW) + msg)


def err(msg: str) -> None:
    """Print an error message prefixed with a cross."""
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
