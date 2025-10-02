from __future__ import annotations

from pathlib import Path

from ..io_safe import delete_all_backups, remove_config
from ..logging_utils import log_event as _log_event_default
from ..ui import warn as _warn_default
from ..updates import (
    check_for_updates as _check_updates_default,
    _log_update_sources,
    _report_update_status,
)


def handle_early_exits(
    args,
    home: Path,
    *,
    config_targets: list[Path],
    current_version: str,
    install_origin: str,
    update_sources: list[str],
    log_cb=_log_update_sources,
    report_cb=_report_update_status,
    log_fn=_log_event_default,
    warn_fn=_warn_default,
    check_fn=_check_updates_default,
) -> bool:
    """Process early-exit flags that should terminate the run.

    Returns True if an early-exit path was handled and the caller should exit.
    """
    # Remove/cleanup requests
    if getattr(args, "remove_config", False) or getattr(
        args, "remove_config_no_bak", False
    ):
        remove_config(getattr(args, "remove_config_no_bak", False))
        return True
    if getattr(args, "delete_all_backups", False):
        delete_all_backups(getattr(args, "confirm_delete_backups", False))
        return True

    # Forced update check path
    sources_arg = update_sources or None
    if getattr(args, "check_updates", False):
        try:
            result = check_fn(current_version, home, force=True, sources=sources_arg)
        except Exception as exc:
            warn_fn(f"Update check failed: {exc}")
            log_fn(
                "update_check_failed",
                forced=True,
                origin=install_origin,
                error=str(exc),
            )
            return True
        log_cb(result, forced=True, origin=install_origin)
        report_cb(
            result, current_version, forced=True, verbose=True, origin=install_origin
        )
        log_fn(
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


def maybe_run_update_check(
    args,
    home: Path,
    *,
    current_version: str,
    install_origin: str,
    update_sources: list[str],
    log_cb=_log_update_sources,
    report_cb=_report_update_status,
    log_fn=_log_event_default,
    warn_fn=_warn_default,
    check_fn=_check_updates_default,
) -> None:
    """Run a background update check unless suppressed by flags."""
    if getattr(args, "no_update_check", False):
        return
    try:
        result = check_fn(current_version, home, sources=(update_sources or None))
    except Exception as exc:
        log_fn(
            "update_check_failed",
            forced=False,
            origin=install_origin,
            error=str(exc),
        )
        if getattr(args, "verbose", False):
            warn_fn(f"Update check failed: {exc}")
        return
    log_cb(result, forced=False, origin=install_origin)
    report_cb(
        result,
        current_version,
        forced=False,
        verbose=getattr(args, "verbose", False),
        origin=install_origin,
    )
    log_fn(
        "update_check_completed",
        forced=False,
        origin=install_origin,
        newer=result.has_newer,
        used_cache=result.used_cache,
        sources=",".join(update_sources),
    )
