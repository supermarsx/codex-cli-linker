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


def test_clear_screen_exception(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(
        cli.os, "system", lambda cmd: (_ for _ in ()).throw(Exception("boom"))
    )
    # Should swallow exception
    cli.clear_screen()


def test_version_unknown(monkeypatch):
    cli = load_cli()

    def boom(_):
        raise Exception("no dist")

    monkeypatch.setattr(cli, "pkg_version", boom)

    class P(type(Path("."))):  # create Path-like class
        pass

    orig_exists = Path.exists

    def fake_exists(self):
        if self.name == "pyproject.toml":
            return False
        return orig_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    assert cli.get_version().endswith("+unknown")


def test_linkerstate_load_invalid_json(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json}", encoding="utf-8")
    st = cli.LinkerState.load(bad)
    assert isinstance(st, cli.LinkerState)
    out = capsys.readouterr().out
    assert "Could not load" in out


def test_http_get_json_http_error(monkeypatch):
    cli = load_cli()

    def raise_http(*a, **k):
        raise urllib.error.HTTPError("http://x", 400, "Bad", {}, None)

    monkeypatch.setattr(cli.urllib.request, "urlopen", raise_http)
    data, err = cli.http_get_json("http://x")
    assert data is None and "HTTP 400" in err


def test_detect_base_url_none(monkeypatch, capsys):
    cli = load_cli()
    monkeypatch.setattr(cli, "http_get_json", lambda url: (None, "err"))
    base = cli.detect_base_url(["http://a", "http://b"])
    assert base is None
    out = capsys.readouterr().out
    assert "not responding" in out and "No server auto" in out


def test_try_auto_ctx_early_return(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "http_get_json", lambda url: ({}, None))
    assert cli.try_auto_context_window("http://x", "m") == 0


def test_backup_warn(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    p = tmp_path / "f.txt"
    p.write_text("x", encoding="utf-8")

    def fake_replace(self, other):
        raise RuntimeError("nope")

    monkeypatch.setattr(Path, "replace", fake_replace)
    cli.backup(p)
    out = capsys.readouterr().out
    assert "Backup failed" in out


def test_build_cfg_azure_queryparams():
    cli = load_cli()
    state = cli.LinkerState(base_url=cli.DEFAULT_LMSTUDIO)
    args = cli.parse_args(
        [
            "--approval-policy",
            "on-failure",
            "--sandbox-mode",
            "workspace-write",
            "--model-context-window",
            "0",
            "--model-max-output-tokens",
            "0",
            "--project-doc-max-bytes",
            "1",
            "--tui",
            "table",
            "--azure-api-version",
            "2024-06-01",
        ]
    )
    cfg = cli.build_config_dict(state, args)
    assert (
        cfg["model_providers"][state.provider]["query_params"]["api-version"]
        == "2024-06-01"
    )


def test_to_toml_wide_coverage():
    cli = load_cli()
    cfg = {
        "model": "m",
        "model_provider": "p",
        "approval_policy": "on-failure",
        "sandbox_mode": "workspace-write",
        "file_opener": "vscode",
        "model_reasoning_effort": "low",
        "model_reasoning_summary": "auto",
        "model_verbosity": "medium",
        "model_context_window": 128,
        "model_max_output_tokens": 256,
        "project_doc_max_bytes": 1,
        "tui": "table",
        "hide_agent_reasoning": True,
        "show_raw_agent_reasoning": False,
        "model_supports_reasoning_summaries": False,
        "chatgpt_base_url": "http://x",
        "experimental_resume": "",
        "experimental_instructions_file": "",
        "experimental_use_exec_command_tool": False,
        "responses_originator_header_internal_override": "",
        "preferred_auth_method": "apikey",
        "profile": "prof",
        "disable_response_storage": False,
        "tools": {"web_search": True, "count": 2, "name": "z"},
        "history": {"persistence": "file", "max_bytes": 0},
        "sandbox_workspace_write": {
            "writable_roots": ["/a"],
            "enabled": False,
            "note": "hi",
            "max_files": 5,
        },
        "model_providers": {
            "p": {
                "name": "Prov",
                "base_url": "http://x",
                "wire_api": "chat",
                "api_key_env_var": "ENV",
                "request_max_retries": 1,
                "stream_max_retries": 2,
                "stream_idle_timeout_ms": 3,
                "query_params": {"api-version": "2024-06-01", "empty": ""},
            },
            "empty": {},
        },
        "profiles": {
            "prof": {
                "model": "m",
                "model_provider": "p",
                "model_context_window": 128,
                "model_max_output_tokens": 256,
                "approval_policy": True,  # exercise bool branch
            },
            "empty": {},
        },
    }
    out = cli.to_toml(cfg)
    assert "tui" not in out
    assert "[model_providers.p]" in out and "api-version" in out and "empty" not in out
    assert "[model_providers.empty]" not in out
    assert "[profiles.empty]" not in out and "approval_policy = True" in out


def test_to_yaml_top_scalar():
    cli = load_cli()
    y = cli.to_yaml("scalar")
    assert '"scalar"' in y


def test_find_codex_cmd_found(monkeypatch):
    cli = load_cli()

    def which(name):
        return "/usr/bin/codex" if name in ("codex", "codex.cmd") else None

    monkeypatch.setattr(cli.shutil, "which", which)
    res = cli.find_codex_cmd()
    assert res and res[0].startswith("codex")


def test_launch_codex_keyboard_interrupt(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "ensure_codex_cli", lambda: ["codex"])
    monkeypatch.setattr(cli.os, "name", "posix")
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    assert cli.launch_codex("p") == 130


def test_prompt_yes_no_invalid_branch(monkeypatch, capsys):
    cli = load_cli()
    inputs = iter(["maybe", "y"])  # invalid then yes
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert cli.prompt_yes_no("Q?", default=True) is True
    out = capsys.readouterr().out
    assert "Please answer y or n." in out


def test_logging_remote_with_query_and_https(monkeypatch):
    cli = load_cli()
    captured = {}

    def fake_emit(self, record):
        captured["secure"] = getattr(self, "secure", None)
        captured["host"] = self.host
        captured["url"] = self.url
        captured["msg"] = record.getMessage()

    import logging

    monkeypatch.setattr(cli.logging.handlers.HTTPHandler, "emit", fake_emit)
    args = cli.parse_args(["--log-remote", "https://example.com/log?x=1"])
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.warning("remote-log")
    assert captured["host"] == "example.com" and captured["url"].endswith("?x=1")


def test_main_interactive_paths(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    # Force custom provider path and interactive prompts; also exercise context window detection paths
    monkeypatch.setattr(
        cli, "pick_base_url", lambda state, auto: "http://localhost:9999/v1"
    )
    monkeypatch.setattr(
        cli, "list_models", lambda base: ["a", "b"]
    )  # for interactive model pick
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    # try_auto_context_window returns >0 to set the value
    monkeypatch.setattr(cli, "try_auto_context_window", lambda base, m: 42)

    # Inputs: provider id, model pick '1', approval '1', reasoning effort choose out-of-range '5' then clamped, summary '1', verbosity '2', sandbox '2', show raw 'y'
    inputs = iter(["myprov", "1", "1", "5", "1", "2", "2", "y"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--model-context-window",
            "0",
            "--dry-run",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert (
        "Configured profile" in out and "myprov" in out and "context window: 42" in out
    )


def test_auto_model_index_out_of_range(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "http_get_json", lambda url, timeout=3.0: ({"data": [{"id": "m1"}]}, None)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "99",
            "--model-context-window",
            "0",
            "--dry-run",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert 'model = "m1"' in out


def test_context_window_exception_path(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "http_get_json", lambda url, timeout=3.0: ({"data": [{"id": "m1"}]}, None)
    )
    monkeypatch.setattr(
        cli,
        "try_auto_context_window",
        lambda base, m: (_ for _ in ()).throw(Exception("boom")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--model-context-window",
            "0",
            "--dry-run",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Context window detection failed" in out


def test_non_dry_run_writes_files(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "http_get_json", lambda url, timeout=3.0: ({"data": [{"id": "m1"}]}, None)
    )
    # ensure model-context-window is set by try_auto_context_window
    monkeypatch.setattr(cli, "try_auto_context_window", lambda base, m: 7)
    # Run with JSON and YAML outputs to exercise write + backup paths
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
    )
    cli.main()
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "config.yaml").exists()


def test_try_auto_ctx_nested_parameters(monkeypatch):
    cli = load_cli()
    data = {"data": [{"id": "m9", "parameters": {"max_context_window": 8192}}]}
    monkeypatch.setattr(cli, "http_get_json", lambda url: (data, None))
    assert cli.try_auto_context_window("http://x", "m9") == 8192


def test_to_toml_empty_provider_only():
    cli = load_cli()
    out = cli.to_toml(
        {
            "model": "m",
            "model_provider": "p",
            "sandbox_mode": "workspace-write",
            "model_context_window": 0,
            "model_max_output_tokens": 0,
            "project_doc_max_bytes": 0,
            "history": {"persistence": "file", "max_bytes": 0},
            "model_providers": {"empty": {}},
            "profiles": {"p": {"model": "m", "model_provider": "p"}},
        }
    )
    assert "[model_providers.empty]" not in out


def test_to_toml_empty_query_params_removed():
    cli = load_cli()
    out = cli.to_toml(
        {
            "model": "m",
            "model_provider": "p",
            "sandbox_mode": "workspace-write",
            "model_context_window": 0,
            "model_max_output_tokens": 0,
            "project_doc_max_bytes": 0,
            "history": {"persistence": "file", "max_bytes": 0},
            "model_providers": {
                "p": {
                    "name": "P",
                    "base_url": "http://x",
                    "wire_api": "chat",
                    "api_key_env_var": "E",
                    "query_params": {},
                }
            },
            "profiles": {"p": {"model": "m", "model_provider": "p"}},
        }
    )
    assert "query_params" not in out


def test_get_version_pyproject_read_error(monkeypatch):
    cli = load_cli()
    # Fail dist lookup to force pyproject path
    monkeypatch.setattr(
        cli, "pkg_version", lambda name: (_ for _ in ()).throw(Exception("x"))
    )
    # Simulate pyproject exists but read fails
    orig_exists = Path.exists

    def fake_exists(self):
        return True if self.name == "pyproject.toml" else orig_exists(self)

    def fake_read_text(self, encoding="utf-8"):
        raise RuntimeError("read error")

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "read_text", fake_read_text)
    assert cli.get_version().endswith("+unknown")


def test_auto_branch_model_list_error(monkeypatch, tmp_path):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    # list_models will raise
    monkeypatch.setattr(
        cli, "list_models", lambda base: (_ for _ in ()).throw(Exception("boom"))
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--dry-run",
        ],
    )
    try:
        cli.main()
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 2


def test_main_env_key_name_explicit(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    monkeypatch.setattr(cli, "detect_base_url", lambda: cli.DEFAULT_LMSTUDIO)
    monkeypatch.setattr(
        cli, "http_get_json", lambda url, timeout=3.0: ({"data": [{"id": "m1"}]}, None)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--auto",
            "--model-index",
            "0",
            "--env-key-name",
            "TESTKEY",
            "--dry-run",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "Configured profile" in out


def test_interactive_pick_error(monkeypatch, tmp_path):
    cli = load_cli()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "clear_screen", lambda: None)
    monkeypatch.setattr(cli, "banner", lambda: None)
    # Force custom provider path but we'll bypass prompts by providing base-url
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--base-url",
            "http://localhost:9999/v1",
            "--dry-run",
        ],
    )
    # pick_model_interactive raises
    inputs = iter(["myprov"])  # provider id prompt
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    monkeypatch.setattr(
        cli,
        "pick_model_interactive",
        lambda base, last: (_ for _ in ()).throw(Exception("x")),
    )
    try:
        cli.main()
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 2


def test_ensure_codex_cli_install_success(monkeypatch):
    cli = load_cli()
    calls = {"check": 0}
    # First lookup returns None (before install), second returns npx
    state = {"count": 0}

    def fake_find():
        state["count"] += 1
        return None if state["count"] == 1 else ["npx", "codex"]

    monkeypatch.setattr(cli, "find_codex_cmd", fake_find)
    monkeypatch.setattr(
        cli.shutil, "which", lambda n: "/usr/bin/npm" if n == "npm" else None
    )

    def ok_check_call(cmd):
        calls["check"] += 1
        return 0

    monkeypatch.setattr(cli.subprocess, "check_call", ok_check_call)
    assert cli.ensure_codex_cli() == ["npx", "codex"]
    assert calls["check"] == 1
