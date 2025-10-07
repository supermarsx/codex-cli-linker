"""Typed containers for update-check results.

These dataclasses represent the per-source outcome (``SourceResult``) and the
aggregated check across sources (``UpdateCheckResult``). They are serializable
for simple JSON caching via ``to_cache``/``from_cache``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


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
