import datetime
import importlib.util
import sys
from pathlib import Path
import pytest


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_backup_creates_unique_versions(monkeypatch, tmp_path):
    cli = load_cli()
    target = tmp_path / "config.toml"
    target.write_text("one", encoding="utf-8")

    class Time1:
        @staticmethod
        def now():
            return datetime.datetime(2025, 1, 1, 12, 30)

    class Time2:
        @staticmethod
        def now():
            return datetime.datetime(2025, 1, 1, 12, 31)

    monkeypatch.setattr(cli, "datetime", Time1)
    cli.backup(target)

    target.write_text("two", encoding="utf-8")
    monkeypatch.setattr(cli, "datetime", Time2)
    cli.backup(target)

    backups = sorted(p.name for p in tmp_path.glob("config.toml.*.bak"))
    assert backups == [
        "config.toml.20250101-1230.bak",
        "config.toml.20250101-1231.bak",
    ]


def test_delete_backups_requires_confirmation(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    bak = tmp_path / "old.bak"
    bak.write_text("1", encoding="utf-8")
    cli = load_cli()
    monkeypatch.setattr(
        sys,
        "argv",
        ["codex-cli-linker.py", "--delete-all-backups"],
    )
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "confirm-delete-backups" in out
    assert bak.exists()


def test_delete_backups_with_confirmation(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    b1 = tmp_path / "a.bak"
    b2 = tmp_path / "b.bak"
    b1.write_text("1", encoding="utf-8")
    b2.write_text("2", encoding="utf-8")
    cli = load_cli()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--delete-all-backups",
            "--confirm-delete-backups",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Deleted 2 backup file" in out
    assert not any(tmp_path.glob("*.bak"))


def test_remove_config_creates_backup(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cfg = tmp_path / "config.toml"
    cfg.write_text("1", encoding="utf-8")
    for m in list(sys.modules):
        if m.startswith("codex_linker") or m == "codex_cli_linker":
            sys.modules.pop(m)
    cli = load_cli()
    monkeypatch.setattr(
        sys,
        "argv",
        ["codex-cli-linker.py", "--remove-config"],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Removed 1 config file" in out
    assert not cfg.exists()
    assert list(tmp_path.glob("config.toml.*.bak"))


def test_remove_config_no_bak(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cfg = tmp_path / "config.toml"
    cfg.write_text("1", encoding="utf-8")
    for m in list(sys.modules):
        if m.startswith("codex_linker") or m == "codex_cli_linker":
            sys.modules.pop(m)
    cli = load_cli()
    monkeypatch.setattr(
        sys,
        "argv",
        ["codex-cli-linker.py", "--remove-config-no-bak"],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Removed 1 config file" in out
    assert not cfg.exists()
    assert not list(tmp_path.glob("*.bak"))
