"""Install-origin detection helpers.

This module provides a focused utility, :func:`detect_install_origin`, used to
infer how the tool is being executed (binary, PyPI, Homebrew, Scoop, Git, or
source). The result is used to choose appropriate update sources and improve
logging/reporting context in the CLI.

Notes
- Pure stdlib; safe to import early during startup.
- Avoids raising for environment-specific path errors and falls back to
  "source" when uncertainty remains.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def detect_install_origin(
    module_path: Optional[Path] = None,
    *,
    frozen: Optional[bool] = None,
    max_git_depth: int = 4,
) -> str:
    """Best-effort detection of how the tool is being executed.

    Parameters
    - module_path: Optional path used for detection in tests.
    - frozen: Override for ``sys.frozen`` (used by PyInstaller).
    - max_git_depth: Parent directory traversal limit when hunting for ``.git``.

    Returns
    - One of: ``binary``, ``pypi``, ``homebrew``, ``scoop``, ``git``, ``source``.
    """

    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return "binary"

    module_path = (module_path or Path(__file__).resolve()).resolve()
    parents = list(module_path.parents)

    def _is_within(path: Path, root: Optional[Path]) -> bool:
        if not root:
            return False
        try:
            path.relative_to(root)
            return True
        except ValueError:  # pragma: no cover
            return False

    def _safe_path(value: Optional[str]) -> Optional[Path]:
        if not value:
            return None
        try:
            return Path(value).resolve()
        except Exception:  # pragma: no cover
            return None

    brew_cellar_path = _safe_path(os.environ.get("HOMEBREW_CELLAR"))
    brew_prefix_path = _safe_path(os.environ.get("HOMEBREW_PREFIX"))
    brew_prefix_cellar = brew_prefix_path / "Cellar" if brew_prefix_path else None
    if _is_within(module_path, brew_cellar_path) or _is_within(
        module_path, brew_prefix_cellar
    ):
        return "homebrew"

    scoop_home = _safe_path(os.environ.get("SCOOP"))
    scoop_global = _safe_path(os.environ.get("SCOOP_GLOBAL"))
    for scoop_root in (scoop_home, scoop_global):
        if _is_within(module_path, scoop_root):
            return "scoop"

    for parent in parents:
        name = parent.name.lower()
        if name in {"site-packages", "dist-packages"}:
            return "pypi"
        if name in {"cellar", "homebrew"}:
            return "homebrew"
        if name == "scoop":
            return "scoop"
        if name == "apps" and parent.parent and parent.parent.name.lower() == "scoop":
            return "scoop"

    for depth, parent in enumerate(parents, start=1):
        if (parent / ".git").exists():
            return "git"
        if depth >= max_git_depth:
            break
    return "source"
