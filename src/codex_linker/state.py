"""Serializable CLI state (persisted between runs).

This module defines :class:`LinkerState`, a small dataclass used to carry
non‑secret preferences between runs (e.g., last base URL, provider, profile).

Design notes:
 - ``api_key`` is intentionally excluded from on‑disk state to avoid persisting
   secrets; authentication data belongs in ``auth.json`` instead.
 - Persistence format is a simple JSON object at a path chosen by callers.
 - Methods never raise for I/O or decoding errors; they print a short message
   and return a default state to keep the CLI resilient.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path


@dataclass
class LinkerState:
    """Mutable, persistable CLI state.

    Attributes capture the user's last selections and preferences. All fields
    are optional and default to benign values. Secrets (``api_key``) are kept
    in‑memory only and are never written by :meth:`save`.
    """

    base_url: str = ""
    provider: str = ""
    model: str = ""
    profile: str = ""
    api_key: str = ""
    env_key: str = ""
    approval_policy: str = ""
    sandbox_mode: str = ""
    reasoning_effort: str = ""
    reasoning_summary: str = ""
    verbosity: str = ""
    disable_response_storage: bool = False
    no_history: bool = False
    history_max_bytes: int = 0

    def save(self, path: Path) -> None:
        """Write state to ``path`` as JSON.

        - Creates parent directories as needed.
        - Preserves non‑state keys already present in the file.
        - Excludes ``api_key`` from persisted content.
        - Never raises; prints a short error and returns on failure.
        """

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_state = asdict(self)
            new_state.pop("api_key", None)
            # Preserve any non-state keys already present in the file
            try:
                existing = (
                    json.loads(path.read_text(encoding="utf-8"))
                    if path.exists()
                    else {}
                )
                if not isinstance(existing, dict):
                    existing = {}
            except Exception:
                existing = {}
            # Overwrite only known state fields
            for f in fields(self):
                if f.name == "api_key":
                    continue
                existing[f.name] = new_state.get(f.name, f.default)
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:  # pragma: no cover
            print(f"Could not save state: {e}")

    @classmethod
    def load(cls, path: Path) -> "LinkerState":
        """Load state from ``path``; fallback to defaults on error.

        Returns a new :class:`LinkerState` instance. If the file does not
        exist, is unreadable, or contains an unexpected structure, a default
        instance is returned and a short message is printed for visibility.
        """

        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover
            print(f"Could not load state: {e}")
            return cls()
        if not isinstance(data, dict):
            print("Could not load state: invalid format")
            return cls()
        kwargs = {f.name: data.get(f.name, f.default) for f in fields(cls)}
        return cls(**kwargs)


__all__ = ["LinkerState"]
