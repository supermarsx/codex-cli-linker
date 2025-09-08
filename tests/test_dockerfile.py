from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDockerfile(unittest.TestCase):
    def setUp(self) -> None:
        self.dockerfile = REPO_ROOT / "Dockerfile"

    def test_dockerfile_exists(self):
        self.assertTrue(
            self.dockerfile.exists(),
            msg="Dockerfile should exist at repo root",
        )

    def test_dockerfile_basic_contents(self):
        content = self.dockerfile.read_text(encoding="utf-8", errors="ignore")
        # Base image
        self.assertIn("FROM python:", content)
        # Either copy single-file CLI or install src package
        has_single = "COPY codex-cli-linker.py" in content
        has_pkg = ("COPY src" in content) and ("pip install ." in content)
        self.assertTrue(
            has_single or has_pkg,
            msg="Dockerfile should copy CLI script or src/ and install package",
        )
        # Sets CODEX_HOME for container
        self.assertIn("CODEX_HOME=", content)
        # Installs Codex CLI via npm
        self.assertIn("npm install -g @openai/codex-cli", content)
        # Has entrypoint to run the CLI (either direct script or console entry)
        self.assertTrue(
            'ENTRYPOINT ["python", "./codex-cli-linker.py"]' in content
            or 'ENTRYPOINT ["codex-cli-linker"]' in content
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
