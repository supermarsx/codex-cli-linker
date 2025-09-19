import importlib.util
import sys
from pathlib import Path
import unittest


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


class TestToYaml(unittest.TestCase):
    def test_nested_dicts_and_lists(self):
        cli = load_cli()
        cfg = {
            "a": {"b": [1, {"c": 2}], "d": True},
            "e": ["x", {"y": "z"}],
        }
        y = cli.to_yaml(cfg)
        expected_lines = [
            "a:",
            "  b:",
            "    - 1",
            "    -",
            "      c: 2",
            "  d: true",
            "e:",
            '  - "x"',
            "  -",
            '    y: "z"',
        ]
        self.assertEqual(y.splitlines(), expected_lines)
        self.assertTrue(y.endswith("\n"))


if __name__ == "__main__":  # pragma: no cover - convenience
    unittest.main()
