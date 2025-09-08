import os
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


def test_main_non_dry_run_writes_and_summary(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    # direct writes into temp CODEX_HOME by overriding constants
    monkeypatch.setattr(cli, "CODEX_HOME", tmp_path)
    monkeypatch.setattr(cli, "CONFIG_TOML", tmp_path / "config.toml")
    monkeypatch.setattr(cli, "CONFIG_JSON", tmp_path / "config.json")
    monkeypatch.setattr(cli, "CONFIG_YAML", tmp_path / "config.yaml")
    # avoid UI and network
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "list_models", lambda *a, **k: ["m1", "m2"]
    )  # model index 0 used
    monkeypatch.setattr(cli, "try_auto_context_window", lambda *a, **k: 42)
    # run main to write TOML/JSON/YAML
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--json",
            "--yaml",
        ],
        raising=False,
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Summary:" in out and "target:" in out and "profile:" in out
    # files exist
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "config.yaml").exists()


def test_configure_logging_file_and_remote_error(tmp_path, monkeypatch):
    cli = load_cli()
    log_path = tmp_path / "app.log"
    # file handler
    cli.configure_logging(
        verbose=True,
        log_file=str(log_path),
        log_json=False,
        log_remote=None,
        log_level=None,
    )
    cli.log_event("file_route", provider="lmstudio")
    data = log_path.read_text(encoding="utf-8")
    assert "file_route" in data

    # remote handler error (subprocess to hit async path)
    code = (
        "import os,sys; from codex_linker import impl as I; from logging.handlers import HTTPHandler;\n"
        "orig=HTTPHandler.emit; HTTPHandler.emit=lambda self, rec: (_ for _ in ()).throw(Exception('boom'));\n"
        "I.configure_logging(False,None,False,'http://example.com', log_level='info'); I.log_event('x');\n"
        "HTTPHandler.emit=orig\n"
    )
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)  # ensure async path
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src") + (
        os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else ""
    )
    res = __import__("subprocess").run([sys.executable, "-c", code], env=env)
    assert res.returncode == 0
