from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..utils import http_get_json
from .types import SourceResult, UpdateCheckResult
from .version import is_version_newer

_GITHUB_API = "https://api.github.com/repos/supermarsx/codex-cli-linker/releases/latest"
_PYPI_API = "https://pypi.org/pypi/codex-cli-linker/json"
_CACHE_FILE = "update_check.json"
_CACHE_TTL = timedelta(hours=6)
_ALLOWED_SOURCES = ("github", "pypi")


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


def _normalize_sources(sources: Optional[Sequence[str]]) -> List[str]:
    if not sources:
        return list(_ALLOWED_SOURCES)
    normalized: List[str] = []
    for name in sources:
        key = str(name).strip().lower()
        if key in _ALLOWED_SOURCES and key not in normalized:
            normalized.append(key)
    return normalized or list(_ALLOWED_SOURCES)


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
            info.get("package_url") if isinstance(info.get("package_url"), str) else None
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

