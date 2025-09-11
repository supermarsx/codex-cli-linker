import sys
from pathlib import Path
import importlib.util


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_supports_color_env(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert cli.supports_color() is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.supports_color() is False
