from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple

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


def log_event(event: str, level: int = 20, **fields) -> None:
    """Structured log helper. Uses stdlib logging; never raises."""
    import logging

    try:
        logging.getLogger().log(level, event, extra={"event": event, **fields})
    except Exception:
        pass


__all__ = ["get_version", "http_get_json", "log_event"]
