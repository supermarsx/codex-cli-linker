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

from .spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
    DEFAULT_OPENAI,
    DEFAULT_OPENROUTER,
    DEFAULT_ANTHROPIC,
    DEFAULT_GROQ,
    DEFAULT_MISTRAL,
    DEFAULT_DEEPSEEK,
    DEFAULT_COHERE,
)

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

    # Fallback: read version from pyproject.toml without third-party deps.
    pyproj = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproj.exists():
        try:
            text = pyproj.read_text(encoding="utf-8")
            # Try stdlib tomllib if available (Python 3.11+)
            try:
                import tomllib  # type: ignore

                data = tomllib.loads(text)  # type: ignore[name-defined]
                ver = (data.get("project") or {}).get("version")
                if isinstance(ver, str) and ver:
                    return ver
            except Exception:
                # Fall back to a simple regex scan within [project] section
                import re

                m = re.search(r"(?ms)^\[project\].*?^version\s*=\s*\"([^\"]+)\"", text)
                if m:
                    return m.group(1)
        except Exception:
            # Reading/parsing pyproject failed; continue to default
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


_PROVIDER_PREFIXES = {
    DEFAULT_LMSTUDIO.rsplit("/v1", 1)[0]: "lmstudio",
    DEFAULT_OLLAMA.rsplit("/v1", 1)[0]: "ollama",
    DEFAULT_VLLM.rsplit("/v1", 1)[0]: "vllm",
    DEFAULT_TGWUI.rsplit("/v1", 1)[0]: "tgwui",
    DEFAULT_TGI_8080.rsplit("/v1", 1)[0]: "tgi",
    DEFAULT_TGI_3000.rsplit("/v1", 1)[0]: "tgi",
    DEFAULT_OPENROUTER_LOCAL.rsplit("/v1", 1)[0]: "openrouter",
    DEFAULT_OPENROUTER.rsplit("/v1", 1)[0]: "openrouter-remote",
    DEFAULT_ANTHROPIC.rsplit("/v1", 1)[0]: "anthropic",
    DEFAULT_GROQ.rsplit("/v1", 1)[0]: "groq",
    DEFAULT_MISTRAL.rsplit("/v1", 1)[0]: "mistral",
    DEFAULT_DEEPSEEK.rsplit("/v1", 1)[0]: "deepseek",
    DEFAULT_COHERE.rsplit("/v2", 1)[0]: "cohere",
    DEFAULT_OPENAI.rsplit("/v1", 1)[0]: "openai",
}


def resolve_provider(base_url: str) -> str:
    """Map a base URL to a known provider id or ``custom``."""
    for prefix, pid in _PROVIDER_PREFIXES.items():
        if base_url.startswith(prefix):
            return pid
    # Azure pattern match
    try:
        from urllib.parse import urlparse

        netloc = urlparse(base_url).netloc.lower()
        if netloc.endswith(".openai.azure.com"):
            return "azure"
    except Exception:
        pass
    return "custom"


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
    finder = getattr(
        sys.modules.get("codex_cli_linker"), "find_codex_cmd", find_codex_cmd
    )
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


def launch_codex(profile: str, ensure: Optional[Callable[[], List[str]]] = None) -> int:
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
    "resolve_provider",
    "log_event",
    "pkg_version",
    "find_codex_cmd",
    "ensure_codex_cli",
    "launch_codex",
    "os",
    "shutil",
    "subprocess",
]
