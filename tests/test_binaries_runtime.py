"""Runtime checks for packaged binaries.

These tests execute a built binary (if present) with ``--help`` and
``--version`` to validate that it starts correctly across platforms and
packaging modes. They intentionally avoid network calls and write activity by
isolating ``CODEX_HOME`` to a temporary directory.

Test discovery is environment-aware:
 - You can point ``CODEX_CLI_LINKER_BIN`` at a specific binary to test.
 - Otherwise, the tests search common locations (``dist/``, repo root, PATH).

When no binary is available, the tests are skipped cleanly.
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _candidate_binaries() -> list:
    """Return plausible binary paths of the packaged CLI for runtime checks.

    Search order:
    - Explicit env var: ``CODEX_CLI_LINKER_BIN``
    - ``dist/`` folder in repo (common PyInstaller output)
    - project root candidates
    - PATH lookup for installed console script
    """
    cands = []

    env_bin = os.environ.get("CODEX_CLI_LINKER_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.exists() and p.is_file():
            cands.append(p)

    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist"
    if dist_dir.exists():
        for name in (
            "codex-cli-linker",
            "codex-cli-linker-macos-arm64",
            "codex-cli-linker-macos-x64",
            "codex-cli-linker-linux-x64",
            "codex-cli-linker-windows-x64.exe",
        ):
            p = dist_dir / name
            if p.exists() and p.is_file():
                cands.append(p)

    # Project root candidates (useful for ad-hoc local builds)
    for name in (
        "codex-cli-linker",
        "codex-cli-linker.exe",
    ):
        p = repo_root / name
        if p.exists() and p.is_file():
            cands.append(p)

    # PATH lookup for installed console entrypoint
    which_bin = shutil.which("codex-cli-linker")
    if which_bin:
        cands.append(Path(which_bin))

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for p in cands:
        s = str(p)
        if s not in seen:
            seen.add(s)
            uniq.append(p)
    return uniq


def _run(cmd: list, extra_env: dict | None = None, timeout: int = 20) -> tuple[int, str, str]:
    """Run a command and capture output.

    Returns (exit_code, stdout, stderr). Does not raise on non-zero exit.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=timeout,
            check=False,
            text=True,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as e:
        return 127, "", str(e)


@unittest.skipUnless(_candidate_binaries(), "No codex-cli-linker binary available to test")
class TestPackagedBinariesRuntime(unittest.TestCase):
    def setUp(self) -> None:
        # Isolate any incidental file writes (defensive; we only call safe flags)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env = {
            "CODEX_HOME": self.tmpdir.name,
            # Prefer non-interactive output if ever expanded
            "TERM": os.environ.get("TERM", "xterm"),
        }
        # Prefer UTF-8 consistent behavior
        if platform.system() == "Windows":
            self.env.setdefault("PYTHONIOENCODING", "utf-8")

        self.bins = _candidate_binaries()
        # Sanity: ensure we have at least one candidate at test time
        self.assertTrue(self.bins)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_help_runs(self) -> None:
        """Binary starts and prints help text."""
        for b in self.bins:
            with self.subTest(binary=str(b)):
                code, out, err = _run([str(b), "--help"], self.env)
                self.assertEqual(code, 0, msg=f"--help failed: stderr={err!r}")
                # Expect some help text mentioning the tool name or common flags
                text = out or err
                self.assertTrue(
                    any(k in text.lower() for k in ("usage", "codex", "--auto")),
                    msg=f"Unexpected help output: {text!r}")

    def test_version_runs(self) -> None:
        """Binary prints a version string and exits successfully.

        For frozen builds without package metadata, we accept a reasonable
        fallback such as ``0.0.0+unknown``.
        """
        # Try to extract declared version from pyproject for a loose match
        repo_root = Path(__file__).resolve().parents[1]
        pyproj = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r"^version\s*=\s*\"([^\"]+)\"", pyproj, flags=re.M)
        declared = m.group(1) if m else None

        for b in self.bins:
            with self.subTest(binary=str(b)):
                code, out, err = _run([str(b), "--version"], self.env)
                self.assertEqual(code, 0, msg=f"--version failed: stderr={err!r}")
                text = (out + "\n" + err).strip()
                self.assertTrue(text, msg="No version output produced")
                # Prefer declared match when available, but tolerate bundled fallback
                if declared and declared not in text:
                    # Accept common fallback marker from frozen builds
                    self.assertRegex(
                        text, r"unknown|\d+\.\d+(?:\.\d+)?", msg=f"Unexpected version text: {text!r}"
                    )
