from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDockerCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.compose = REPO_ROOT / "docker-compose.yml"

    def test_compose_exists(self):
        self.assertTrue(self.compose.exists(), msg="docker-compose.yml should exist")

    def test_service_and_mounts(self):
        content = self.compose.read_text(encoding="utf-8", errors="ignore")
        # Basic keys
        self.assertIn("services:", content)
        self.assertIn("codex-linker:", content)
        # Env var wiring
        self.assertIn("CODEX_HOME=/data/.codex", content)
        # Host mount to persist configs
        # Use a tolerant check for ${HOME}/.codex:/data/.codex
        self.assertTrue(
            "/.codex:/data/.codex" in content,
            msg="Expected host ~/.codex mapped to /data/.codex",
        )
        # Default command auto
        self.assertIn('command: ["--auto"]', content)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
