import importlib.util
import re
import sys
from pathlib import Path


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def read_pyproject_version() -> str:
    txt = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    m = re.search(r"(?ms)^\[project\].*?^version\s*=\s*\"([^\"]+)\"", txt)
    assert m, "version not found in pyproject.toml"
    return m.group(1)


def test_version_from_pyproject(monkeypatch, capsys):
    cli = load_cli()

    # Ensure distribution lookup fails so fallback to pyproject is used
    def boom(_name: str):
        raise Exception("not installed")

    monkeypatch.setattr(cli, "pkg_version", boom)

    monkeypatch.setattr(
        sys, "argv", ["codex-cli-linker.py", "--version"], raising=False
    )
    cli.main()
    out = capsys.readouterr().out.strip()
    assert out == read_pyproject_version()


def test_version_from_distribution(monkeypatch, capsys):
    cli = load_cli()

    monkeypatch.setattr(cli, "pkg_version", lambda name: "9.9.9")
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "-V"], raising=False)
    cli.main()
    out = capsys.readouterr().out.strip()
    assert out == "9.9.9"
