from __future__ import annotations

"""Update source selection.

Translates a detected install origin into a list of update sources to query.
This isolates policy so that other modules can remain focused on fetching and
reporting.
"""

from typing import List


def determine_update_sources(origin: str) -> List[str]:
    """Return ordered update sources for the provided install ``origin``."""

    origin = (origin or "").lower()
    if origin == "pypi":
        return ["pypi"]
    if origin in {"binary", "git", "homebrew", "brew", "scoop"}:
        return ["github"]
    return ["github", "pypi"]
