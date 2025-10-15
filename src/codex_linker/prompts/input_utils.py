"""Low-level input helpers for interactive prompts.

Provides a small toolkit for building TUI-like prompts without dependencies:
- Optional emoji stripping via ``set_emojis_enabled`` + ``fmt``
- Safe input wrappers that propagate Ctrl-C
- ``prompt_choice`` with arrow-key navigation on supported terminals
- Small parsers for CSV/JSON/env key-value inputs used by editors
"""

from __future__ import annotations

import sys
import os
from typing import List, Optional, Dict, Any

from ..ui import (
    err,
    c,
    BOLD,
    CYAN,
    GRAY,
    supports_color,
    RED,
    YELLOW,
    GREEN,
    BLUE,
    MAGENTA,
)

NO_EMOJIS = False
# Set of emoji/symbol codepoints used in prompts. Use base characters so
# combined sequences like "⚙️" (gear + VS16) are removed by per-char filtering.
_EMOJIS = {
    "⏹",
    "⚙",
    "⛭",
    "✅",
    "✍",
    "✏",
    "✓",
    "✗",
    "❌",
    "❎",
    "➕",
    "➤",
    "⬅",
    "⬇",
    "🌐",
    "🎛",
    "🏠",
    "🏷",
    "👤",
    "💾",
    "📝",
    "🔌",
    "🔐",
    "🔙",
    "🗑",
    "🚀",
    "🧭",
    "🧰",
    "🪄",
}


def set_emojis_enabled(enabled: bool) -> None:
    """Enable or disable emojis globally for interactive prompts.

    Controlled by a module-level flag so that all prompt helpers render
    consistently. The hub sets this based on ``--no-emojis``.
    """
    global NO_EMOJIS
    NO_EMOJIS = not enabled


def fmt(text: str) -> str:
    """Return text with emoji-aware formatting fixes.

    - When emojis are enabled: collapses accidental extra spaces after emojis.
    - When emojis are disabled: strips emojis, removes composition markers, and
      collapses repeated spaces created by removal, then trims edges.
    """
    if not NO_EMOJIS:
        s = str(text)
        # Only normalize spacing if the string contains emojis/symbols we track
        if any(ch in _EMOJIS or ch in ("\u200d", "\ufe0f") for ch in s):
            return " ".join(s.split())
        return s
    out_chars = []
    for ch in text:
        # Skip emoji/symbols and common composition markers
        if ch in _EMOJIS or ch in ("\u200d", "\ufe0f"):
            continue
        out_chars.append(ch)
    cleaned = "".join(out_chars)
    # Collapse runs of whitespace to a single space and trim
    cleaned = " ".join(cleaned.split())
    return cleaned


def _safe_input(prompt: str) -> str:
    """input() that propagates Ctrl-C so callers can decide behavior."""
    try:
        return input(prompt)
    except KeyboardInterrupt:
        print()
        raise


def _is_null_input(s: str) -> bool:
    """Return True when the input represents an explicit null value.

    Accepts the string ``"null"`` (case-insensitive) and ignores surrounding
    whitespace. Used by editors to allow clearing optional fields.
    """
    try:
        return s.strip().lower() == "null"
    except Exception:
        return False


def _arrow_choice(prompt: str, options: List[str]) -> Optional[int]:
    """Arrow-key navigable selector. Returns index or None if unsupported."""
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        return None
    try:
        if os.name == "nt":
            import msvcrt as _ms  # type: ignore

            del _ms
        else:
            import termios as _t  # type: ignore
            import tty as _ty  # type: ignore

            del _t, _ty
    except Exception:
        return None

    idx = 0
    n = len(options)
    use_color = supports_color() and not os.environ.get("NO_COLOR")
    numbuf: str = ""

    def draw() -> None:
        print(c(fmt(prompt), BOLD))
        palette = [RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA]
        for i, opt in enumerate(options):
            marker = "➤" if i == idx else " "
            line = f" {marker} {fmt(opt)}"
            if use_color:
                col = palette[i % len(palette)] if palette else CYAN
                if i == idx:
                    print(c(line, col + BOLD))
                else:
                    print(c(line, col))
            else:
                print(line)

    def read_key() -> str:
        if os.name == "nt":
            import msvcrt  # type: ignore

            ch = msvcrt.getwch()
            if ch == "\x03":  # Ctrl-C
                return "CTRL_C"
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch == "\x1b":
                return "ESC"
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                mapping = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}
                return mapping.get(ch2, "")
            if ch == "\x08":
                return "BACKSPACE"
            return ch
        else:
            import termios  # type: ignore
            import tty  # type: ignore

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch1 = sys.stdin.read(1)
                if ch1 == "\x03":  # Ctrl-C
                    return "CTRL_C"
                if ch1 in ("\r", "\n"):
                    return "ENTER"
                if ch1 == "\x7f":
                    return "BACKSPACE"
                if ch1 != "\x1b":
                    return ch1
                ch2 = sys.stdin.read(1)
                if ch2 != "[":
                    return "ESC"
                ch3 = sys.stdin.read(1)
                mapping = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
                return mapping.get(ch3, "")
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    draw()
    while True:
        key = read_key()
        if key == "CTRL_C":
            print()
            raise KeyboardInterrupt
        if key == "ESC":
            print()
            return -1
        if key == "ENTER":
            if numbuf and numbuf.isdigit():
                sel = int(numbuf)
                if 1 <= sel <= n:
                    print()
                    return sel - 1
            print()
            return idx
        if key in ("UP", "k"):
            idx = (idx - 1) % n
            numbuf = ""
        elif key in ("DOWN", "j"):
            idx = (idx + 1) % n
            numbuf = ""
        elif key == "BACKSPACE":
            numbuf = numbuf[:-1]
            if numbuf.isdigit() and 1 <= int(numbuf) <= n:
                idx = int(numbuf) - 1
        elif key and key.isdigit():
            numbuf += key
            if numbuf.isdigit() and 1 <= int(numbuf) <= n:
                idx = int(numbuf) - 1
        if supports_color():
            sys.stdout.write(f"\x1b[{n+1}F")
            sys.stdout.flush()
        draw()


def prompt_choice(prompt: str, options: List[str]) -> int:
    """Present a numbered/arrow menu and return the selected index.

    Supports arrow navigation when the terminal allows raw input; otherwise
    falls back to a numbered list. ESC attempts to select a "Back" item when
    present, or raises KeyboardInterrupt so callers can decide.
    """
    sel = _arrow_choice(prompt, options)
    if sel is not None:
        if isinstance(sel, int) and sel == -1:
            # ESC pressed: try to select a Back option if present
            back_indices: List[int] = []
            for i, opt in enumerate(options):
                lo = str(opt).lower()
                if "back" in lo or "🏠" in str(opt) or "🔙" in str(opt):
                    back_indices.append(i)
            if back_indices:
                return back_indices[-1]
            # Fallback: bubble up
            raise KeyboardInterrupt
        return sel
    for i, opt in enumerate(options, 1):
        use_color = supports_color() and not os.environ.get("NO_COLOR")
        if use_color:
            palette = [RED, YELLOW, GREEN, CYAN, BLUE, MAGENTA]
            col = palette[(i - 1) % len(palette)]
            print(c(f"  {i}. {fmt(opt)}", col))
        else:
            print(f"  {i}. {fmt(opt)}")
    while True:
        s = _safe_input(f"{fmt(prompt)} [1-{len(options)}]: ").strip()
        if s.isdigit() and 1 <= int(s) <= len(options):
            return int(s) - 1
        err("Invalid choice.")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt a yes/no question with a default, normalizing answers."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        s = _safe_input(f"{question} {suffix} ").strip().lower()
        if not s:
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        err("Please answer y or n.")


def _input_list_csv(prompt: str, default: Optional[List[str]] = None) -> List[str]:
    """Prompt for a CSV list and return a list of trimmed strings.

    Returns ``default`` when empty and a default is provided; otherwise an
    empty list.
    """
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _input_list_json(prompt: str, default: Optional[List[str]] = None) -> List[str]:
    """Prompt for a JSON array and return a list of strings.

    If parsing fails, returns a single-item list with the raw input (or the
    provided default when blank).
    """
    import json as _json

    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    try:
        arr = _json.loads(raw)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    return [raw]


def _input_env_kv(
    prompt: str, default: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Parse ``KEY=VAL`` CSV into a dict, returning ``default`` when blank."""
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return dict(default)
    env: Dict[str, str] = {}
    if not raw:
        return env
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                env[k] = v
    return env


def _parse_brace_kv(raw: str) -> Dict[str, str]:
    """Parse ``{key="value",...}`` or ``key="value",...`` into a dict."""
    s = (raw or "").strip()
    if not s:
        return {}
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    out: Dict[str, str] = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (
                v.startswith("'") and v.endswith("'")
            ):
                if len(v) >= 2:
                    v = v[1:-1]
            if k:
                out[k] = v
    return out


def _print_item_with_desc(label: str, value: Any, desc: str) -> None:
    """Print a label/value pair and an optional gray description beneath."""
    print(f"  {label}: {value}")
    if desc:
        print(c(f"     – {desc}", GRAY))
