from __future__ import annotations

import re
from itertools import zip_longest
from typing import List


def is_version_newer(current: str, candidate: str) -> bool:
    """Heuristic comparison that favours numeric precedence, handles v-prefix."""

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

