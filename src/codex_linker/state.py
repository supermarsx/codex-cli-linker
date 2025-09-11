from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LinkerState:
    base_url: str = ""
    provider: str = ""
    model: str = ""
    profile: str = ""
    ctx_window: int = 0
    env_key: str = ""


__all__ = ["LinkerState"]
