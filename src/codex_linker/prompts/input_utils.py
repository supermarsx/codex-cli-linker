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
_EMOJIS = {"👤","🧰","🔌","⚙️","🚀","🧭","❌","💾","📝","⬅️","🗑️","✏️","🏠","🏷️","✅","⏹️"}


def set_emojis_enabled(enabled: bool) -> None:
    """Enable or disable emojis globally for interactive prompts."""
    global NO_EMOJIS
    NO_EMOJIS = not enabled


def fmt(text: str) -> str:
    """Return text with emojis stripped when disabled."""
    if not NO_EMOJIS:
        return text
    out = []
    for ch in text:
        if ch in _EMOJIS:
            continue
        out.append(ch)
    return "".join(out)


def _safe_input(prompt: str) -> str:
    """input() that propagates Ctrl-C so callers can decide behavior."""
    try:
        return input(prompt)
    except KeyboardInterrupt:
        print()
        raise


def _is_null_input(s: str) -> bool:
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
    raw = input(f"{prompt} ").strip()
    if not raw and default is not None:
        return list(default)
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _input_list_json(prompt: str, default: Optional[List[str]] = None) -> List[str]:
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


def _input_env_kv(prompt: str, default: Optional[Dict[str, str]] = None) -> Dict[str, str]:
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
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                if len(v) >= 2:
                    v = v[1:-1]
            if k:
                out[k] = v
    return out


def _print_item_with_desc(label: str, value: Any, desc: str) -> None:
    print(f"  {label}: {value}")
    if desc:
        print(c(f"     – {desc}", GRAY))
