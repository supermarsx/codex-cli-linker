import importlib.util
import sys
import time
from pathlib import Path


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_detect_base_url_parallel(monkeypatch):
    cli = load_cli()

    def fake_http_get_json(url, timeout=3.0):
        if "1234" in url:
            time.sleep(0.5)
            return None, "slow"
        return {"data": []}, None

    monkeypatch.setattr(cli, "http_get_json", fake_http_get_json)
    start = time.perf_counter()
    base = cli.detect_base_url([cli.DEFAULT_LMSTUDIO, cli.DEFAULT_OLLAMA])
    elapsed = time.perf_counter() - start
    assert base == cli.DEFAULT_OLLAMA
    assert elapsed < 0.3
