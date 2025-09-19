from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path


@dataclass
class LinkerState:
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
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = asdict(self)
            data.pop("api_key", None)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:  # pragma: no cover
            print(f"Could not save state: {e}")

    @classmethod
    def load(cls, path: Path) -> "LinkerState":
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
