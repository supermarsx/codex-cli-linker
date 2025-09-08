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


def test_dry_run_diff_outputs_unified(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    # point CODEX_HOME to temp so config paths resolve inside tmp
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    # create an existing TOML to produce a diff
    (tmp_path / "config.toml").write_text("model='before'\n", encoding="utf-8")
    # Avoid network and prompts
    monkeypatch.setattr(cli, "detect_base_url", lambda *a, **k: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "list_models", lambda *a, **k: ["m1", "m2"]
    )  # used by main when needed
    monkeypatch.setattr(cli, "try_auto_context_window", lambda *a, **k: 0)
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    # Run main with --dry-run --diff
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--dry-run",
            "--diff",
        ],
        raising=False,
    )
    cli.main()
    out = capsys.readouterr().out
    # Unified diff contains '---' and '+++'
    assert "---" in out and "+++" in out


def test_atomic_write_with_backup(tmp_path):
    cli = load_cli()
    target = tmp_path / "file.txt"
    cli.atomic_write_with_backup(target, "one\n")
    assert target.read_text(encoding="utf-8") == "one\n"
    # second write should create a .bak and replace content
    cli.atomic_write_with_backup(target, "two\n")
    assert target.read_text(encoding="utf-8") == "two\n"
    backups = list(tmp_path.glob("file.txt.*.bak"))
    assert backups, "Expected a .bak after overwrite"
