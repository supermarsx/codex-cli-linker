import importlib.util
import json
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


def test_http_get_json_ok(monkeypatch):
    cli = load_cli()

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ok": 1}).encode("utf-8")

    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *a, **k: Resp())
    data, err = cli.http_get_json("http://x")
    assert data == {"ok": 1} and err is None


def test_http_get_json_http_error(monkeypatch):
    cli = load_cli()
    import urllib.error

    def boom(*a, **k):
        raise urllib.error.HTTPError("http://x", 500, "uh oh", {}, None)

    monkeypatch.setattr(cli.urllib.request, "urlopen", boom)
    data, err = cli.http_get_json("http://x")
    assert data is None and "HTTP 500" in err

