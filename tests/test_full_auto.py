import importlib.util
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


def fake_models_response(url, timeout=3.0):
    return {"data": [{"id": "m1"}, {"id": "m2"}]}, None


def test_full_auto_selects_first_model(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()
    monkeypatch.setattr(cli, "http_get_json", fake_models_response)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--full-auto",
            "--dry-run",
            "--model-context-window",
            "1",
        ],
    )
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert 'model = "m1"' in out


def test_model_index_override(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()
    monkeypatch.setattr(cli, "http_get_json", fake_models_response)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--full-auto",
            "--model-index",
            "1",
            "--dry-run",
            "--model-context-window",
            "1",
        ],
    )
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert 'model = "m2"' in out
