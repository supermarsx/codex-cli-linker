import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
import importlib
import importlib.util


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


cli_module = load_cli()

determine_update_sources = cli_module.determine_update_sources
detect_install_origin = cli_module.detect_install_origin
is_version_newer = cli_module.is_version_newer


def load_updates_module():
    if "codex_linker.updates" in sys.modules:
        return sys.modules["codex_linker.updates"]
    return importlib.import_module("codex_linker.updates")


updates = load_updates_module()


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

    def test_alphanumeric_ordering(self) -> None:
        self.assertTrue(is_version_newer("1.2.3a", "1.2.3b"))
        self.assertFalse(is_version_newer("1.2.3beta", "1.2.3alpha"))


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
            formula_dir = cellar / "codex-cli-linker" / "0.1.3"
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


class UpdateCacheTests(unittest.TestCase):
    def test_source_result_from_cache_invalid(self) -> None:
        result = updates.SourceResult.from_cache("github", "not-a-dict")
        self.assertEqual(result.error, "invalid cache")
        self.assertIsNone(result.version)

    def test_normalize_sources_deduplicates(self) -> None:
        normalized = updates._normalize_sources(["GitHub", "github", "unknown", "PyPI"])
        self.assertEqual(normalized, ["github", "pypi"])

    def test_save_and_load_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "update_check.json"
            sources = {
                "github": updates.SourceResult("github", "0.2.0", "https://example"),
            }
            now = datetime.utcnow()
            updates._save_cache(cache_path, now, sources)
            cached, used = updates._load_cache(
                cache_path, now, timedelta(hours=1), ["github"]
            )
            self.assertTrue(used)
            self.assertIn("github", cached)
            self.assertEqual(cached["github"].version, "0.2.0")


class CheckForUpdatesBehaviourTests(unittest.TestCase):
    def test_check_for_updates_force_and_cache_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            calls = []

            def fake_fetch(url, timeout):
                calls.append((url, timeout))
                return updates.SourceResult("github", "0.2.0", url, error=None)

            with mock.patch.dict(
                updates._FETCHERS, {"github": fake_fetch}, clear=False
            ):
                result_force = updates.check_for_updates(
                    "0.1.0", home, force=True, sources=["github"]
                )
                self.assertEqual(len(calls), 1)
                self.assertEqual(result_force.sources[0].version, "0.2.0")
                self.assertFalse(result_force.used_cache)
                result_cached = updates.check_for_updates(
                    "0.1.0", home, force=False, sources=["github"]
                )
                self.assertEqual(len(calls), 1)
                self.assertTrue(result_cached.used_cache)

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
