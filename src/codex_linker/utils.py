from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:  # pragma: no cover
    from importlib.metadata import PackageNotFoundError, version as pkg_version
except Exception:  # pragma: no cover
    PackageNotFoundError = Exception  # type: ignore

    def pkg_version(_: str) -> str:  # type: ignore
        raise PackageNotFoundError


def get_version() -> str:
    """Return installed package version or derive from pyproject.

    Falls back to ``0.0.0+unknown`` when no metadata is available."""
    pv = getattr(sys.modules.get("codex_cli_linker"), "pkg_version", pkg_version)
    try:
        return pv("codex-cli-linker")
    except Exception:
        pass
    try:
        import tomllib

        pyproj = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproj.exists():
            data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
            return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        pass
    return "0.0.0+unknown"


def http_get_json(
    url: str, timeout: float = 3.0
) -> Tuple[Optional[dict], Optional[str]]:
    """Fetch JSON with a short timeout; return (data, error_message)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, str(e)


def find_codex_cmd() -> Optional[List[str]]:
    """Locate the Codex CLI, preferring bare command names.

    Returning command names keeps subprocess invocations predictable and
    simplifies testing where absolute paths may vary.
    """
    for name in ("codex", "codex.cmd"):
        path = shutil.which(name)
        if path and os.path.basename(path).startswith("codex"):
            return [name]
    return ["npx", "codex"] if shutil.which("npx") else None


def ensure_codex_cli() -> List[str]:
    finder = getattr(sys.modules.get("codex_cli_linker"), "find_codex_cmd", find_codex_cmd)
    cmd = finder()
    if cmd:
        return cmd
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Codex CLI is required but npm is missing")
    try:
        subprocess.check_call([npm, "install", "-g", "@openai/codex-cli"])
    except subprocess.CalledProcessError:
        raise SystemExit("Codex CLI install failed")
    cmd = finder()
    if not cmd:
        raise SystemExit("Codex CLI is required but not installed")
    return cmd


def launch_codex(
    profile: str, ensure: Optional[Callable[[], List[str]]] = None
) -> int:
    """Launch the external Codex CLI with the given profile.

    ``ensure`` allows callers (and tests) to supply a custom ``ensure_codex_cli``
    implementation. KeyboardInterrupts are converted into the conventional exit
    code ``130`` instead of bubbling up.
    """
    ensure = ensure or ensure_codex_cli
    cmd = ensure()
    if os.name == "nt":
        cmdline = subprocess.list2cmdline(cmd + ["--profile", profile])
        ps = shutil.which("powershell")
        if ps:
            run_cmd = ["powershell", "-NoLogo", "-NoProfile", "-Command", cmdline]
        else:
            run_cmd = ["cmd", "/c", cmdline]
    else:
        run_cmd = cmd + ["--profile", profile]
    try:
        return subprocess.run(run_cmd).returncode
    except KeyboardInterrupt:
        return 130


def log_event(event: str, level: int = 20, **fields) -> None:
    """Structured log helper. Uses stdlib logging; never raises."""
    import logging

    try:
        logging.getLogger().log(level, event, extra={"event": event, **fields})
    except Exception:
        pass


__all__ = [
    "get_version",
    "http_get_json",
    "log_event",
    "pkg_version",
    "find_codex_cmd",
    "ensure_codex_cli",
    "launch_codex",
    "os",
    "shutil",
    "subprocess",
]
