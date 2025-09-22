import argparse
import json
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


def test_main_update_check_success(monkeypatch, tmp_path):
    import codex_linker.main_flow as main_flow

    cli = load_cli()

    dummy_args = argparse.Namespace(
        remove_config=False,
        remove_config_no_bak=False,
        delete_all_backups=False,
        confirm_delete_backups=False,
        check_updates=True,
        version=False,
        verbose=False,
        log_file=None,
        log_json=False,
        log_remote=None,
        log_level=None,
    )

    result = cli.UpdateCheckResult(
        current_version="0.1.0",
        sources=[
            cli.SourceResult(name="github", version="0.2.0", url="http://release")
        ],
        newer_sources=[],
        used_cache=False,
    )

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(main_flow, "parse_args", lambda: dummy_args)
    monkeypatch.setattr(main_flow, "get_version", lambda: "0.1.0")
    monkeypatch.setattr(main_flow, "detect_install_origin", lambda: "pypi")
    monkeypatch.setattr(
        main_flow, "determine_update_sources", lambda origin: ["github"]
    )
    monkeypatch.setattr(main_flow, "check_for_updates", lambda *a, **k: result)

    events = []
    monkeypatch.setattr(
        main_flow,
        "log_event",
        lambda *a, **k: events.append((a, k)),
    )
    flags = {"log": False, "report": False}
    monkeypatch.setattr(
        main_flow, "_log_update_sources", lambda *a, **k: flags.__setitem__("log", True)
    )
    monkeypatch.setattr(
        main_flow,
        "_report_update_status",
        lambda *a, **k: flags.__setitem__("report", True),
    )
    monkeypatch.setattr(
        main_flow,
        "warn",
        lambda msg: (_ for _ in ()).throw(AssertionError(f"unexpected warn: {msg}")),
    )

    main_flow.main()

    assert flags == {"log": True, "report": True}
    assert any(args[0] == "update_check_completed" for args, _ in events)


def test_main_update_check_failure(monkeypatch, tmp_path):
    cli = load_cli()
    import codex_linker.main_flow as main_flow

    dummy_args = argparse.Namespace(
        remove_config=False,
        remove_config_no_bak=False,
        delete_all_backups=False,
        confirm_delete_backups=False,
        check_updates=True,
        version=False,
        verbose=False,
        log_file=None,
        log_json=False,
        log_remote=None,
        log_level=None,
    )

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(main_flow, "parse_args", lambda: dummy_args)
    monkeypatch.setattr(main_flow, "get_version", lambda: "0.1.0")
    monkeypatch.setattr(main_flow, "detect_install_origin", lambda: "source")
    monkeypatch.setattr(
        main_flow, "determine_update_sources", lambda origin: ["github", "pypi"]
    )

    def fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(main_flow, "check_for_updates", fail)
    events = []
    monkeypatch.setattr(
        main_flow,
        "log_event",
        lambda *a, **k: events.append((a, k)),
    )
    warnings = []
    assert hasattr(cli, "UpdateCheckResult")
    monkeypatch.setattr(main_flow, "warn", lambda msg: warnings.append(msg))

    main_flow.main()

    assert warnings and "Update check failed" in warnings[0]
    assert any(args[0] == "update_check_failed" for args, _ in events)


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
    monkeypatch.setattr(
        cli, "detect_base_url", lambda state, auto: cli.DEFAULT_LMSTUDIO
    )
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
    assert str(tmp_path / "config.toml") in out
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
    proc = cli.subprocess.run(
        [sys.executable, "-c", code], capture_output=True, env=env
    )
    assert proc.returncode == 0


def test_workspace_state_override(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.chdir(workspace)
    monkeypatch.setattr(cli, "CODEX_HOME", home)
    monkeypatch.setattr(cli, "CONFIG_TOML", home / "config.toml")
    monkeypatch.setattr(cli, "CONFIG_JSON", home / "config.json")
    monkeypatch.setattr(cli, "CONFIG_YAML", home / "config.yaml")
    monkeypatch.setattr(cli, "LINKER_JSON", home / "linker_config.json")

    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(
        cli, "detect_base_url", lambda state, auto: cli.DEFAULT_LMSTUDIO
    )
    monkeypatch.setattr(cli, "list_models", lambda *a, **k: ["model-a"])
    monkeypatch.setattr(cli, "try_auto_context_window", lambda *a, **k: 0)

    class DummyUpdates:
        sources = []
        newer_sources = []
        errors = []
        used_cache = False

        @property
        def has_newer(self):
            return False

    monkeypatch.setattr(cli, "check_for_updates", lambda *a, **k: DummyUpdates())
    monkeypatch.setattr(cli, "_log_update_sources", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_report_update_status", lambda *a, **k: None)
    monkeypatch.setattr(cli, "log_event", lambda *a, **k: None)

    writes = []
    monkeypatch.setattr(
        cli, "atomic_write_with_backup", lambda path, content: writes.append(path)
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--workspace-state",
            "--auto",
            "--model-index",
            "0",
        ],
        raising=False,
    )

    cli.main()
    state_path = workspace / ".codex-linker.json"
    assert state_path.exists()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data.get("base_url") == cli.DEFAULT_LMSTUDIO
    assert not (home / "linker_config.json").exists()
