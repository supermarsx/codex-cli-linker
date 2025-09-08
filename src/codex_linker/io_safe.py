"""Safe IO helpers (atomic writes, backups, paths)."""

from codex_cli_linker import (  # type: ignore
    CODEX_HOME,
    CONFIG_TOML,
    CONFIG_JSON,
    CONFIG_YAML,
    LINKER_JSON,
    backup,
    do_backup,
    atomic_write_with_backup,
)

__all__ = [
    "CODEX_HOME",
    "CONFIG_TOML",
    "CONFIG_JSON",
    "CONFIG_YAML",
    "LINKER_JSON",
    "backup",
    "do_backup",
    "atomic_write_with_backup",
]
