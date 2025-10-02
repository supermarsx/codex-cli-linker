from __future__ import annotations

from typing import List


def determine_update_sources(origin: str) -> List[str]:
    """Map an install origin to the update sources we should query."""

    origin = (origin or "").lower()
    if origin == "pypi":
        return ["pypi"]
    if origin in {"binary", "git", "homebrew", "brew", "scoop"}:
        return ["github"]
    return ["github", "pypi"]

