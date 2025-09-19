import sys
from pathlib import Path


def load_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def _common_monkeypatch(monkeypatch, tmp_path):
    cli = load_cli()
    # Direct writes into temp CODEX_HOME by overriding constants and IO/UI hooks
    monkeypatch.setattr(cli, "CODEX_HOME", tmp_path)
    monkeypatch.setattr(cli, "CONFIG_TOML", tmp_path / "config.toml")
    monkeypatch.setattr(cli, "CONFIG_JSON", tmp_path / "config.json")
    monkeypatch.setattr(cli, "CONFIG_YAML", tmp_path / "config.yaml")
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    # Avoid network; provide deterministic models and context window
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(cli, "list_models", lambda *a, **k: ["m1", "m2"])  # index 0
    monkeypatch.setattr(cli, "try_auto_context_window", lambda *a, **k: 256)
    return cli


def test_open_config_prints_vscode_command(monkeypatch, tmp_path, capsys):
    cli = _common_monkeypatch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--open-config",
            "--json",
            "--yaml",
        ],
        raising=False,
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Open config in your editor:" in out
    assert f'code "{tmp_path / "config.toml"}"' in out


def test_open_config_prints_insiders_command(monkeypatch, tmp_path, capsys):
    cli = _common_monkeypatch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--open-config",
            "--file-opener",
            "vscode-insiders",
        ],
        raising=False,
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Open config in your editor:" in out
    assert f'code-insiders "{tmp_path / "config.toml"}"' in out
