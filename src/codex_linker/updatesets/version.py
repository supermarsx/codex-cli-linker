"""Version comparison helpers.

Implements a tolerant semver-ish comparator that prefers numeric precedence,
handles optional leading "v", and compares alphanumeric segments lexically.
Used to decide if a candidate version is newer than the current one.
"""

from __future__ import annotations

import re
from itertools import zip_longest
from typing import List


def is_version_newer(current: str, candidate: str) -> bool:
    """Return True if ``candidate`` is newer than ``current``.

    Both inputs can be loose (e.g., include ``v`` prefix or alphanumeric
    segments). Numeric chunks are compared numerically; others lexicographically.
    Empty/invalid candidate is not considered newer; empty current is.
    """

    current_parts = _version_parts(current)
    candidate_parts = _version_parts(candidate)
    if not candidate_parts:
        return False
    if not current_parts:
        return True
    return _compare_parts(current_parts, candidate_parts) < 0


def _version_parts(version: str) -> List[object]:
    version = (version or "").strip()
    if not version:
        return []
    if version[0] in {"v", "V"}:
        version = version[1:]
    parts: List[object] = []
    for chunk in re.split(r"[.\-+_]", version):
        if not chunk:
            continue
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            parts.append(chunk.lower())
    return parts


def _compare_parts(current: List[object], candidate: List[object]) -> int:
    for cur, cand in zip_longest(current, candidate, fillvalue=0):
        if cur == cand:
            continue
        if isinstance(cur, int) and isinstance(cand, int):
            return -1 if cur < cand else 1
        if isinstance(cur, int):
            return 1
        if isinstance(cand, int):
            return -1
        cur_str = str(cur)
        cand_str = str(cand)
        if cur_str == cand_str:
            continue
        return -1 if cur_str < cand_str else 1
    return 0
