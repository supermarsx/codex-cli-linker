import importlib.util
from pathlib import Path


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


def make_run(monkeypatch, cli, expected_cmd, returncode):
    def fake_run(cmd, **kwargs):
        assert cmd == expected_cmd

        class R:
            pass

        r = R()
        r.returncode = returncode
        return r

    monkeypatch.setattr(cli.subprocess, "run", fake_run)


def test_launch_codex_posix(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "ensure_codex_cli", lambda: ["codex"])
    monkeypatch.setattr(cli.os, "name", "posix")
    make_run(monkeypatch, cli, ["codex", "--profile", "p"], 0)
    assert cli.launch_codex("p") == 0


def test_launch_codex_npx_posix(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "ensure_codex_cli", lambda: ["npx", "codex"])
    monkeypatch.setattr(cli.os, "name", "posix")
    make_run(monkeypatch, cli, ["npx", "codex", "--profile", "p"], 0)
    assert cli.launch_codex("p") == 0


def test_launch_codex_windows_cmd(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "ensure_codex_cli", lambda: ["codex"])
    monkeypatch.setattr(cli.os, "name", "nt")
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    make_run(monkeypatch, cli, ["cmd", "/c", "codex --profile p"], 5)
    assert cli.launch_codex("p") == 5


def test_launch_codex_windows_powershell(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "ensure_codex_cli", lambda: ["codex"])
    monkeypatch.setattr(cli.os, "name", "nt")

    def fake_which(name):
        return "pwsh" if name == "powershell" else None

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    make_run(
        monkeypatch,
        cli,
        ["powershell", "-NoLogo", "-NoProfile", "-Command", "codex --profile p"],
        0,
    )
    assert cli.launch_codex("p") == 0


def test_find_codex_cmd_falls_back_to_npx(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli.os, "name", "posix")

    def fake_which(name):
        return None if name == "codex" else "/usr/bin/npx"

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    assert cli.find_codex_cmd() == ["npx", "codex"]
