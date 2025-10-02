from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .io_safe import atomic_write_with_backup
from .ui import info, ok


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def migrate_configs_to_linker(
    linker_path: Path,
    *,
    config_toml: Path,
    config_json: Path,
    config_yaml: Path,
) -> bool:
    """Consolidate existing config.{toml,json,yaml} into linker_config.json.

    - Never deletes legacy files; only captures their contents.
    - Stores consolidated data under top-level key `configs` while preserving
      existing top-level state fields for backward compatibility.
    - Idempotent: re-runs update the `configs` block when legacy files change.

    Returns True when the linker file is updated.
    """
    # Start with whatever is already in linker_config.json (if anything)
    existing: Dict[str, Any] = {}
    try:
        if linker_path.exists():
            existing_raw = _load_json(linker_path)
            if isinstance(existing_raw, dict):
                existing = dict(existing_raw)
    except Exception:
        existing = {}

    # Build a consolidated view of legacy files
    changed = False
    configs: Dict[str, Any] = dict(existing.get("configs") or {})
    snapshot_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Capture TOML/YAML as raw text to avoid introducing parsers
    if config_toml.exists():
        try:
            toml_text = config_toml.read_text(encoding="utf-8")
        except Exception:
            toml_text = ""
        if configs.get("toml_text") != toml_text:
            configs["toml_text"] = toml_text
            changed = True
    if config_yaml.exists():
        try:
            yaml_text = config_yaml.read_text(encoding="utf-8")
        except Exception:
            yaml_text = ""
        if configs.get("yaml_text") != yaml_text:
            configs["yaml_text"] = yaml_text
            changed = True

    # Capture JSON as a parsed object if valid; else raw text
    if config_json.exists():
        parsed = _load_json(config_json)
        if parsed is not None:
            if configs.get("json") != parsed:
                configs["json"] = parsed
                changed = True
        else:
            try:
                raw = config_json.read_text(encoding="utf-8")
            except Exception:
                raw = ""
            if configs.get("json_text") != raw:
                configs["json_text"] = raw
                changed = True

    if not changed and "configs" in existing:
        # Nothing new to write
        return False

    if changed or "configs" not in existing:
        configs["migrated_at"] = snapshot_time
        existing["configs"] = configs
        # Ensure parent dir exists
        linker_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_with_backup(linker_path, json.dumps(existing, indent=2) + "\n")
        ok(f"Updated {linker_path.name} with consolidated configs")
        info("Legacy files were not modified; backups preserved where applicable.")
        return True

    return False


__all__ = ["migrate_configs_to_linker"]

