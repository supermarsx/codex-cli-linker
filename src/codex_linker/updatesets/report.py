from __future__ import annotations

from ..logging_utils import log_event
from ..ui import info, warn, ok
from .types import UpdateCheckResult


def _label_source(name: str) -> str:
    mapping = {"github": "GitHub", "pypi": "PyPI"}
    return mapping.get(name.lower(), name.title())


def _label_origin(origin: str) -> str:
    mapping = {
        "pypi": "PyPI install",
        "git": "Git checkout",
        "binary": "packaged binary",
        "homebrew": "Homebrew tap",
        "brew": "Homebrew tap",
        "scoop": "Scoop install",
    }
    return mapping.get((origin or "").lower(), origin or "unknown")


def _log_update_sources(result: UpdateCheckResult, forced: bool, origin: str) -> None:
    """Emit structured logs for each update source probed."""
    for src in result.sources:
        log_event(
            "update_check_source",
            source=src.name,
            version=src.version or "",
            error=src.error or None,
            forced=forced,
            origin=origin,
            used_cache=result.used_cache,
        )


def _report_update_status(
    result: UpdateCheckResult,
    current_version: str,
    *,
    forced: bool,
    verbose: bool,
    origin: str,
) -> None:
    """Human-readable summary of update status across sources."""
    origin_label = _label_origin(origin)
    sources_label = ", ".join(_label_source(src.name) for src in result.sources)
    if forced:
        info(f"Current version: {current_version}")
    if (forced or verbose) and sources_label:
        info(f"Detected {origin_label}; checking {sources_label} for updates.")
    elif (forced or verbose) and not sources_label:
        warn(f"No update sources configured for origin '{origin}'.")
    all_failed = len(result.errors) == len(result.sources)
    if forced or verbose or result.has_newer or all_failed:
        for src in result.sources:
            label = _label_source(src.name)
            if src.version:
                info(f"{label} latest: {src.version}")
                if (forced or result.has_newer) and src.url:
                    info(f"{label} release: {src.url}")
            if src.error and (forced or verbose or all_failed):
                warn(f"{label} check error: {src.error}")
    if result.has_newer:
        summary = ", ".join(
            f"{_label_source(src.name)} {src.version}"
            for src in result.newer_sources
            if src.version
        )
        if summary:
            warn(f"Update available ({summary}); current version is {current_version}.")
        else:
            warn(f"Update available; current version is {current_version}.")
    elif forced or (verbose and not result.errors):
        ok("codex-cli-linker is up to date.")


__all__ = ["_log_update_sources", "_report_update_status"]

