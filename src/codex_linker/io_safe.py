"""Safe IO helpers (atomic writes, backups, paths)."""

from __future__ import annotations
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .ui import info, warn, ok

CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
CONFIG_TOML = CODEX_HOME / "config.toml"
CONFIG_JSON = CODEX_HOME / "config.json"
CONFIG_YAML = CODEX_HOME / "config.yaml"
LINKER_JSON = CODEX_HOME / "linker_config.json"


def backup(path: Path) -> Optional[Path]:
    """Backup existing file with a timestamped suffix. Returns backup path if created."""
    if path.exists():
        dt_obj = getattr(sys.modules.get("codex_cli_linker"), "datetime", datetime)
        if hasattr(dt_obj, "now"):
            now_fn = dt_obj.now
        elif hasattr(dt_obj, "datetime") and hasattr(dt_obj.datetime, "now"):
            now_fn = dt_obj.datetime.now  # type: ignore[attr-defined]
        else:  # pragma: no cover - fallback safety
            now_fn = datetime.now
        stamp = now_fn().strftime("%Y%m%d-%H%M")
        bak = path.with_suffix(f"{path.suffix}.{stamp}.bak")
        try:
            path.replace(bak)
            info(f"Backed up existing {path.name} -> {bak.name}")
            return bak
        except Exception as e:  # pragma: no cover
            warn(f"Backup failed: {e}")
    return None


def do_backup(path: Path) -> Optional[Path]:
    """Perform and announce a backup; returns the backup path if created."""
    return backup(path)


def atomic_write_with_backup(path: Path, text: str) -> Optional[Path]:
    """Atomically write UTF-8 text to `path` with fsync and optional .bak."""
    fd, tmppath = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:  # pragma: no cover
                pass
        bak = do_backup(path)
        os.replace(tmppath, path)
        return bak
    except Exception:
        try:
            os.remove(tmppath)
        except Exception:  # pragma: no cover
            pass
        raise


def remove_config(no_backup: bool) -> None:
    """Remove config files, optionally creating .bak backups."""
    paths = [CONFIG_TOML, CONFIG_JSON, CONFIG_YAML]
    removed = 0
    for path in paths:
        if path.exists():
            if no_backup:
                try:
                    path.unlink()
                    info(f"Deleted {path.name}")
                except Exception as e:  # pragma: no cover
                    warn(f"Failed to delete {path}: {e}")
            else:
                do_backup(path)
            removed += 1
    if removed:
        ok(f"Removed {removed} config file(s)")
    else:
        info("No config files found.")


def delete_all_backups(confirm: bool) -> None:
    """Remove every *.bak file under CODEX_HOME when confirmed."""
    home = Path(os.environ.get("CODEX_HOME", str(CODEX_HOME)))
    backups = list(home.rglob("*.bak"))
    if not confirm:
        warn("Refusing to delete backups without --confirm-delete-backups")
        if backups:
            info(f"Found {len(backups)} backup file(s) under {home}")
        sys.exit(1)
    if not backups:
        info("No backup files found.")
        return
    deleted = []
    for bak in backups:
        try:
            bak.unlink()
            deleted.append(bak)
        except Exception as e:  # pragma: no cover
            warn(f"Failed to delete {bak}: {e}")
    ok(f"Deleted {len(deleted)} backup file(s)")
    for bak in deleted:
        print(f"  {bak}")


__all__ = [
    "CODEX_HOME",
    "CONFIG_TOML",
    "CONFIG_JSON",
    "CONFIG_YAML",
    "LINKER_JSON",
    "backup",
    "do_backup",
    "atomic_write_with_backup",
    "remove_config",
    "delete_all_backups",
]
