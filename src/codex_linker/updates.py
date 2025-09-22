from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import zip_longest
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .utils import http_get_json

_GITHUB_API = "https://api.github.com/repos/supermarsx/codex-cli-linker/releases/latest"
_PYPI_API = "https://pypi.org/pypi/codex-cli-linker/json"
_CACHE_FILE = "update_check.json"
_CACHE_TTL = timedelta(hours=6)
_ALLOWED_SOURCES = ("github", "pypi")


@dataclass
class SourceResult:
    """Outcome for a single update source."""

    name: str
    version: Optional[str]
    url: Optional[str]
    error: Optional[str] = None

    def to_cache(self) -> dict:
        return {
            "version": self.version,
            "url": self.url,
            "error": self.error,
        }

    @classmethod
    def from_cache(cls, name: str, data: object) -> "SourceResult":
        if not isinstance(data, dict):
            return cls(name=name, version=None, url=None, error="invalid cache")
        version = data.get("version") if isinstance(data.get("version"), str) else None
        url = data.get("url") if isinstance(data.get("url"), str) else None
        error = data.get("error") if isinstance(data.get("error"), str) else None
        return cls(name=name, version=version, url=url, error=error)


@dataclass
class UpdateCheckResult:
    """Aggregated update check details."""

    current_version: str
    sources: List[SourceResult]
    newer_sources: List[SourceResult]
    used_cache: bool

    @property
    def has_newer(self) -> bool:
        return bool(self.newer_sources)

    @property
    def errors(self) -> List[SourceResult]:
        return [src for src in self.sources if src.error]


def detect_install_origin(
    module_path: Optional[Path] = None,
    *,
    frozen: Optional[bool] = None,
    max_git_depth: int = 4,
) -> str:
    """Best-effort detection of how the tool is being executed.

    Returns one of ``binary``, ``pypi``, ``homebrew``, ``git``, or ``source`` (catch-all).
    ``module_path`` allows tests to provide a synthetic location, and
    ``frozen`` overrides ``sys.frozen`` detection when provided.
    """

    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return "binary"

    module_path = (module_path or Path(__file__).resolve()).resolve()
    parents = list(module_path.parents)

    def _is_within(path: Path, root: Optional[Path]) -> bool:
        if not root:
            return False
        try:
            path.relative_to(root)
            return True
        except ValueError:  # pragma: no cover - depends on path layout
            return False

    def _safe_path(value: Optional[str]) -> Optional[Path]:
        if not value:
            return None
        try:
            return Path(value).resolve()
        except Exception:  # pragma: no cover - environment-specific paths
            return None

    brew_cellar_path = _safe_path(os.environ.get("HOMEBREW_CELLAR"))
    brew_prefix_path = _safe_path(os.environ.get("HOMEBREW_PREFIX"))
    brew_prefix_cellar = brew_prefix_path / "Cellar" if brew_prefix_path else None
    if _is_within(module_path, brew_cellar_path) or _is_within(
        module_path, brew_prefix_cellar
    ):
        return "homebrew"

    scoop_home = _safe_path(os.environ.get("SCOOP"))
    scoop_global = _safe_path(os.environ.get("SCOOP_GLOBAL"))
    for scoop_root in (scoop_home, scoop_global):
        if _is_within(module_path, scoop_root):
            return "scoop"

    for parent in parents:
        name = parent.name.lower()
        if name in {"site-packages", "dist-packages"}:
            return "pypi"
        if name in {"cellar", "homebrew"}:
            return "homebrew"
        if name == "scoop":
            return "scoop"
        if name == "apps" and parent.parent and parent.parent.name.lower() == "scoop":
            return "scoop"

    for depth, parent in enumerate(parents, start=1):
        if (parent / ".git").exists():
            return "git"
        if depth >= max_git_depth:
            break
    return "source"


def determine_update_sources(origin: str) -> List[str]:
    """Map an install origin to the update sources we should query."""

    origin = origin.lower()
    if origin == "pypi":
        return ["pypi"]
    if origin in {"binary", "git", "homebrew", "brew", "scoop"}:
        return ["github"]
    return list(_ALLOWED_SOURCES)


def check_for_updates(
    current_version: str,
    home: Path,
    *,
    force: bool = False,
    github_url: str = _GITHUB_API,
    pypi_url: str = _PYPI_API,
    cache_ttl: timedelta = _CACHE_TTL,
    timeout: float = 3.0,
    sources: Optional[Sequence[str]] = None,
) -> UpdateCheckResult:
    """Return update information from configured sources.

    Results are cached under ``home`` to keep network usage light. ``force``
    bypasses the cache and refreshes the requested sources.
    """

    requested = _normalize_sources(sources)
    now = datetime.utcnow()
    cache_path = home / _CACHE_FILE

    if force:
        cached: Dict[str, SourceResult] = {}
        cache_used = False
    else:
        cached, cache_used = _load_cache(cache_path, now, cache_ttl, requested)

    results: Dict[str, SourceResult] = dict(cached)
    refreshed = False

    for name in requested:
        if force or name not in cached:
            fetcher = _FETCHERS[name]
            endpoint = github_url if name == "github" else pypi_url
            results[name] = fetcher(endpoint, timeout)
            refreshed = True

    if force or refreshed:
        _save_cache(cache_path, now, results)

    ordered_results = [results[name] for name in requested]
    newer = [
        src
        for src in ordered_results
        if src.version and is_version_newer(current_version, src.version)
    ]
    used_cache = (not force) and cache_used and bool(cached)
    return UpdateCheckResult(
        current_version=current_version,
        sources=ordered_results,
        newer_sources=newer,
        used_cache=used_cache,
    )


def is_version_newer(current: str, candidate: str) -> bool:
    """Heuristic comparison that favours numeric precedence, handles "v" prefix."""

    current_parts = _version_parts(current)
    candidate_parts = _version_parts(candidate)
    if not candidate_parts:
        return False
    if not current_parts:
        return True
    return _compare_parts(current_parts, candidate_parts) < 0


def _normalize_sources(sources: Optional[Sequence[str]]) -> List[str]:
    if not sources:
        return list(_ALLOWED_SOURCES)
    normalized: List[str] = []
    for name in sources:
        key = str(name).strip().lower()
        if key in _ALLOWED_SOURCES and key not in normalized:
            normalized.append(key)
    return normalized or list(_ALLOWED_SOURCES)


def _version_parts(version: str) -> List[object]:
    version = version.strip()
    if not version:
        return []
    if version[0] in {"v", "V"}:
        version = version[1:]
    parts: List[object] = []
    for chunk in re.split(r"[.\-+_]", version):
        if not chunk:
            continue
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            parts.append(chunk.lower())
    return parts


def _compare_parts(current: List[object], candidate: List[object]) -> int:
    for cur, cand in zip_longest(current, candidate, fillvalue=0):
        if cur == cand:
            continue
        if isinstance(cur, int) and isinstance(cand, int):
            return -1 if cur < cand else 1
        if isinstance(cur, int):
            return 1
        if isinstance(cand, int):
            return -1
        cur_str = str(cur)
        cand_str = str(cand)
        if cur_str == cand_str:
            continue
        return -1 if cur_str < cand_str else 1
    return 0


def _fetch_github(url: str, timeout: float) -> SourceResult:
    data, error = http_get_json(url, timeout=timeout)
    if not data:
        return SourceResult("github", version=None, url=None, error=error)
    version = data.get("tag_name") or data.get("name")
    if isinstance(version, str):
        version = version.strip()
    else:
        version = None
    html_url = data.get("html_url") or data.get("url")
    if isinstance(html_url, str):
        html_url = html_url.strip()
    else:
        html_url = None
    return SourceResult("github", version=version, url=html_url, error=error)


def _fetch_pypi(url: str, timeout: float) -> SourceResult:
    data, error = http_get_json(url, timeout=timeout)
    if not data:
        return SourceResult("pypi", version=None, url=None, error=error)
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    version = info.get("version") if isinstance(info.get("version"), str) else None
    project_url = (
        info.get("project_url") if isinstance(info.get("project_url"), str) else None
    )
    if not project_url:
        project_url = (
            info.get("package_url")
            if isinstance(info.get("package_url"), str)
            else None
        )
    if not project_url:
        project_url = "https://pypi.org/project/codex-cli-linker/"
    return SourceResult("pypi", version=version, url=project_url, error=error)


def _load_cache(
    path: Path,
    now: datetime,
    cache_ttl: timedelta,
    requested: Iterable[str],
) -> Tuple[Dict[str, SourceResult], bool]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, False
    checked_at = raw.get("checked_at")
    if not isinstance(checked_at, str):
        return {}, False
    try:
        ts = datetime.fromisoformat(checked_at)
    except Exception:
        return {}, False
    if now - ts > cache_ttl:
        return {}, False
    sources_raw = raw.get("sources")
    if not isinstance(sources_raw, dict):
        return {}, False
    results: Dict[str, SourceResult] = {}
    for name in requested:
        entry = sources_raw.get(name)
        if entry is not None:
            results[name] = SourceResult.from_cache(name, entry)
    return results, bool(results)


def _save_cache(path: Path, now: datetime, sources: Dict[str, SourceResult]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checked_at": now.isoformat(),
            "sources": {name: src.to_cache() for name, src in sources.items()},
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


_FETCHERS = {
    "github": _fetch_github,
    "pypi": _fetch_pypi,
}


__all__ = [
    "check_for_updates",
    "determine_update_sources",
    "detect_install_origin",
    "is_version_newer",
    "SourceResult",
    "UpdateCheckResult",
]
