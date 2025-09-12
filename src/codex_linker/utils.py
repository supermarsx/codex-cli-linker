from __future__ import annotations
import json
import os
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import List, Optional, Tuple

try:  # pragma: no cover
    from importlib.metadata import PackageNotFoundError, version as pkg_version
except Exception:  # pragma: no cover
    PackageNotFoundError = Exception  # type: ignore

    def pkg_version(_: str) -> str:  # type: ignore
        raise PackageNotFoundError


def get_version() -> str:
    """Return installed package version or '0.0.0'."""
    try:
        return pkg_version("codex-cli-linker")
    except PackageNotFoundError:  # pragma: no cover - when running from source
        return "0.0.0"


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
    for name in ("codex", "codex.cmd"):
        path = shutil.which(name)
        if path:
            return [path]
    npx = shutil.which("npx")
    return [npx, "codex"] if npx else None


def ensure_codex_cli() -> List[str]:
    cmd = find_codex_cmd()
    if cmd:
        return cmd
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Codex CLI is required but npm is missing")
    try:
        subprocess.check_call([npm, "install", "-g", "@openai/codex-cli"])
    except subprocess.CalledProcessError:
        raise SystemExit("Codex CLI install failed")
    cmd = find_codex_cmd()
    if not cmd:
        raise SystemExit("Codex CLI is required but not installed")
    return cmd


def launch_codex(profile: str) -> int:
    cmd = ensure_codex_cli()
    if os.name == "nt":
        cmdline = subprocess.list2cmdline(cmd + ["--profile", profile])
        ps = shutil.which("powershell")
        if ps:
            run_cmd = [ps, "-NoLogo", "-NoProfile", "-Command", cmdline]
        else:
            run_cmd = ["cmd", "/c", cmdline]
    else:
        run_cmd = cmd + ["--profile", profile]
    return subprocess.run(run_cmd).returncode


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
