import importlib.util
import sys
import urllib.error
from pathlib import Path


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_config_url_applies_defaults(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"approval_policy": "untrusted", "sandbox_mode": "read-only"}'

    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda url, timeout=3.0: Resp())
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
            "--config-url",
            "http://example.com/defs.json",
            "--model-context-window",
            "1",
            "--dry-run",
        ],
    )
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert 'approval_policy = "untrusted"' in out
    assert 'sandbox_mode = "read-only"' in out


def test_config_url_fetch_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()

    def boom(url, timeout=3.0):
        raise urllib.error.URLError("bad url")

    monkeypatch.setattr(cli.urllib.request, "urlopen", boom)
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
            "--config-url",
            "http://example.com/defs.json",
            "--model-context-window",
            "1",
            "--dry-run",
        ],
    )
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    cli.main()
    out = capsys.readouterr().out
    assert 'approval_policy = "on-failure"' in out
    assert "Failed to fetch config defaults" in out
