from __future__ import annotations

from pathlib import Path

from ..io_safe import delete_all_backups, remove_config
from ..logging_utils import log_event
from ..ui import warn
from ..updates import check_for_updates
from ..updates_helpers import _log_update_sources, _report_update_status


def handle_early_exits(args, home: Path, *, config_targets: list[Path], current_version: str,
                       install_origin: str, update_sources: list[str]) -> bool:
    """Process early-exit flags that should terminate the run.

    Returns True if an early-exit path was handled and the caller should exit.
    """
    # Remove/cleanup requests
    if getattr(args, "remove_config", False) or getattr(args, "remove_config_no_bak", False):
        remove_config(getattr(args, "remove_config_no_bak", False))
        return True
    if getattr(args, "delete_all_backups", False):
        delete_all_backups(getattr(args, "confirm_delete_backups", False))
        return True

    # Forced update check path
    sources_arg = update_sources or None
    if getattr(args, "check_updates", False):
        try:
            result = check_for_updates(current_version, home, force=True, sources=sources_arg)
        except Exception as exc:
            warn(f"Update check failed: {exc}")
            log_event(
                "update_check_failed",
                forced=True,
                origin=install_origin,
                error=str(exc),
            )
            return True
        _log_update_sources(result, forced=True, origin=install_origin)
        _report_update_status(result, current_version, forced=True, verbose=True, origin=install_origin)
        log_event(
            "update_check_completed",
            forced=True,
            origin=install_origin,
            newer=result.has_newer,
            used_cache=result.used_cache,
            sources=",".join(update_sources),
        )
        return True
    # Simple version print
    if getattr(args, "version", False):
        print(current_version)
        return True
    return False


def maybe_run_update_check(args, home: Path, *, current_version: str, install_origin: str,
                           update_sources: list[str]) -> None:
    """Run a background update check unless suppressed by flags."""
    if getattr(args, "no_update_check", False):
        return
    from ..updates import check_for_updates
    try:
        result = check_for_updates(current_version, home, sources=(update_sources or None))
    except Exception as exc:
        log_event(
            "update_check_failed",
            forced=False,
            origin=install_origin,
            error=str(exc),
        )
        if getattr(args, "verbose", False):
            warn(f"Update check failed: {exc}")
        return
    _log_update_sources(result, forced=False, origin=install_origin)
    _report_update_status(
        result, current_version, forced=False, verbose=getattr(args, "verbose", False), origin=install_origin
    )
    log_event(
        "update_check_completed",
        forced=False,
        origin=install_origin,
        newer=result.has_newer,
        used_cache=result.used_cache,
        sources=",".join(update_sources),
    )

