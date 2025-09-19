import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_cli_linker import (
    determine_update_sources,
    detect_install_origin,
    is_version_newer,
)


class VersionComparisonTests(unittest.TestCase):
    def test_numeric_progression(self) -> None:
        self.assertTrue(is_version_newer("1.0.0", "1.0.1"))
        self.assertTrue(is_version_newer("0.9", "1.0"))
        self.assertTrue(is_version_newer("1.2.3", "v1.2.4"))

    def test_same_version_not_newer(self) -> None:
        self.assertFalse(is_version_newer("1.2.3", "1.2.3"))
        self.assertFalse(is_version_newer("1.10.0", "1.2.0"))

    def test_prerelease_ordering(self) -> None:
        self.assertFalse(is_version_newer("1.2.3", "1.2.3-beta"))
        self.assertTrue(is_version_newer("1.2.3-beta", "1.2.3"))

    def test_unknown_base_version(self) -> None:
        self.assertTrue(is_version_newer("0.0.0+unknown", "0.1.0"))
        self.assertFalse(is_version_newer("", ""))


class InstallOriginDetectionTests(unittest.TestCase):
    def test_detects_binary_when_frozen(self) -> None:
        origin = detect_install_origin(Path("/nonexistent"), frozen=True)
        self.assertEqual(origin, "binary")

    def test_detects_pypi_from_site_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_path = (
                Path(tmp) / "lib" / "site-packages" / "codex_linker" / "updates.py"
            )
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.touch()
            origin = detect_install_origin(module_path, frozen=False)
            self.assertEqual(origin, "pypi")

    def test_detects_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "project"
            (repo / ".git").mkdir(parents=True, exist_ok=True)
            module_path = repo / "src" / "codex_linker" / "updates.py"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.touch()
            origin = detect_install_origin(module_path, frozen=False)
            self.assertEqual(origin, "git")

    def test_detects_homebrew_via_cellar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cellar = Path(tmp) / "Cellar"
            formula_dir = cellar / "codex-cli-linker" / "0.1.2"
            module_path = (
                formula_dir
                / "lib"
                / "python3.11"
                / "site-packages"
                / "codex_linker"
                / "updates.py"
            )
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.touch()
            with mock.patch.dict(
                os.environ, {"HOMEBREW_CELLAR": str(cellar)}, clear=False
            ):
                origin = detect_install_origin(module_path, frozen=False)
            self.assertEqual(origin, "homebrew")

    def test_detects_scoop_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scoop_root = Path(tmp) / "scoop"
            module_path = (
                scoop_root
                / "apps"
                / "codex-cli-linker"
                / "current"
                / "codex_linker"
                / "updates.py"
            )
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.touch()
            env = {"SCOOP": str(scoop_root)}
            with mock.patch.dict(os.environ, env, clear=False):
                origin = detect_install_origin(module_path, frozen=False)
            self.assertEqual(origin, "scoop")

    def test_falls_back_to_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_path = Path(tmp) / "src" / "codex_linker" / "updates.py"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.touch()
            origin = detect_install_origin(module_path, frozen=False)
            self.assertEqual(origin, "source")


class UpdateSourceSelectionTests(unittest.TestCase):
    def test_pypi_origin(self) -> None:
        self.assertEqual(determine_update_sources("pypi"), ["pypi"])

    def test_git_origin(self) -> None:
        self.assertEqual(determine_update_sources("git"), ["github"])

    def test_binary_origin(self) -> None:
        self.assertEqual(determine_update_sources("binary"), ["github"])

    def test_homebrew_origin(self) -> None:
        self.assertEqual(determine_update_sources("homebrew"), ["github"])
        self.assertEqual(determine_update_sources("brew"), ["github"])

    def test_scoop_origin(self) -> None:
        self.assertEqual(determine_update_sources("scoop"), ["github"])

    def test_unknown_origin_defaults(self) -> None:
        self.assertEqual(determine_update_sources("source"), ["github", "pypi"])
        self.assertEqual(determine_update_sources("custom"), ["github", "pypi"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
