import datetime
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
