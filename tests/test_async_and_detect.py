import sys
import time
import subprocess
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


def test_log_remote_async_in_subprocess():
    # Exercise async buffered handler by running in a clean subprocess
    code = (
        "import sys; from codex_linker import impl as I;\n"
        "I.configure_logging(False,None,False,'http://example.com', log_level='info');\n"
        "I.log_event('subproc_test', provider='lmstudio');\n"
    )
    import os

    repo_src = str(Path(__file__).resolve().parents[1] / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = repo_src + (
        os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else ""
    )
    res = subprocess.run([sys.executable, "-c", code], env=env)
    assert res.returncode == 0


def test_detect_base_url_cancels_slow(monkeypatch):
    cli = load_cli()

    def fake_http(url, timeout=3.0):
        # simulate two candidates: slow then fast
        if "slow" in url:
            time.sleep(0.5)
            return None, "slow"
        return {"data": []}, None

    monkeypatch.setattr(cli, "http_get_json", fake_http)
    start = time.perf_counter()
    base = cli.detect_base_url(["http://slow/v1", "http://fast/v1"])
    elapsed = time.perf_counter() - start
    assert base == "http://fast/v1"
    assert elapsed < 0.5
