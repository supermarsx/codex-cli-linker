"""Argument definitions: Backup and cleanup flags."""

from __future__ import annotations

import argparse


def add_backup_args(p: argparse.ArgumentParser) -> None:
    backups = p.add_argument_group("Backups")
    backups.add_argument(
        "-db",
        "--delete-all-backups",
        action="store_true",
        help="Remove all *.bak files under CODEX_HOME",
    )
    backups.add_argument(
        "-dc",
        "--confirm-delete-backups",
        action="store_true",
        help="Actually delete backups when --delete-all-backups is used",
    )
    backups.add_argument(
        "-rc",
        "--remove-config",
        action="store_true",
        help="Backup and remove existing config files",
    )
    backups.add_argument(
        "-rN",
        "--remove-config-no-bak",
        action="store_true",
        help="Remove config files without creating backups",
    )


__all__ = ["add_backup_args"]
