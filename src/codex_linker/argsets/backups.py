"""Argument definitions: Backup and cleanup flags.

Provides a small group of safety-focused options for cleaning up backup files
and removing existing configs. Deletion requires explicit confirmation to
avoid accidental data loss.
"""

from __future__ import annotations

import argparse


def add_backup_args(p: argparse.ArgumentParser) -> None:
    """Attach backup/cleanup arguments to the parser.

    Options
    - ``--delete-all-backups``: remove all ``*.bak`` under ``CODEX_HOME``
    - ``--confirm-delete-backups``: required to actually perform deletion
    - ``--remove-config``: backup and remove existing config files
    - ``--remove-config-no-bak``: remove config files without creating backups
    """
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
