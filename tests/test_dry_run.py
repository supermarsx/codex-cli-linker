import importlib.util
import sys
from pathlib import Path


def load_cli(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_dry_run_prints_and_writes_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--base-url",
            "http://localhost:1234/v1",
            "--model",
            "foo",
            "--auto",
            "--json",
            "--yaml",
            "--dry-run",
            "--model-context-window",
            "1",
        ],
    )
    # Avoid noisy screen clearing/banner
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert 'model = "foo"' in out
    assert '"model": "foo"' in out
    assert 'model_provider: "lmstudio"' in out or "model_provider: lmstudio" in out
    assert not (tmp_path / "config.toml").exists()
    assert not (tmp_path / "config.json").exists()
    assert not (tmp_path / "config.yaml").exists()
    assert not (tmp_path / "linker_config.json").exists()
