import json
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


def test_to_toml_writes_optional_sections():
    cli = load_cli()
    state = cli.LinkerState()
    args = cli.parse_args(
        [
            "--auto",
            "--base-url",
            cli.DEFAULT_LMSTUDIO,
            "--provider",
            "lmstudio",
            "--profile",
            "p1",
            "--model",
            "m1",
            "--tools-web-search",
            "--no-history",
            "--history-max-bytes",
            "1024",
            "--model-context-window",
            "99",
            "--model-max-output-tokens",
            "11",
            "--azure-api-version",
            "2024-05-01",
        ]
    )
    cfg = cli.build_config_dict(state, args)
    t = cli.to_toml(cfg)
    assert "[tools]" in t and "web_search = true" in t
    assert "[history]" in t and "max_bytes = 1024" in t
    assert "[model_providers.lmstudio]" in t
    assert "api_key_env_var =" in t
    assert (
        'query_params = {\n\t"api-version" = "2024-05-01"\n}' in t or "api-version" in t
    )
    # Profile section rendered
    assert "[profiles." in t


def test_configure_logging_jsonformatter_fields(capsys):
    cli = load_cli()
    # configure JSON logging on stdout
    cli.configure_logging(
        verbose=False, log_file=None, log_json=True, log_remote=None, log_level="info"
    )
    cli.log_event(
        "unit_test", provider="lmstudio", model="m1", path="/tmp/test", duration_ms=1
    )
    out = capsys.readouterr().out.strip()
    js = json.loads(out)
    assert js["event"] == "unit_test"
    assert js["provider"] == "lmstudio" and js["model"] == "m1"
    assert js["path"] == "/tmp/test" and js["duration_ms"] == 1


def test_try_auto_context_window_nested(monkeypatch):
    cli = load_cli()

    def fake_models(url):
        return {
            "data": [
                {"id": "m0", "meta": {"parameters": {"context_window": 77}}},
                {"id": "m1", "metadata": {"n_ctx": 66}},
            ]
        }, None

    monkeypatch.setattr(cli, "http_get_json", lambda url, timeout=3.0: fake_models(url))
    assert cli.try_auto_context_window("http://localhost:1234/v1", "m0") == 77
    assert (
        cli.try_auto_context_window("http://localhost:1234/v1", "mX") == 77
        or cli.try_auto_context_window("http://localhost:1234/v1", "mX") == 66
    )


def test_main_yes_errors(monkeypatch, capsys):
    cli = load_cli()
    # Missing base-url when not auto
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--yes"], raising=False)
    try:
        cli.main()
    except SystemExit as e:
        assert e.code == 2

    # Missing model with --yes (auto but no model/model-index)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        sys, "argv", ["codex-cli-linker.py", "--yes", "--auto"], raising=False
    )
    try:
        cli.main()
    except SystemExit as e:
        assert e.code == 2
