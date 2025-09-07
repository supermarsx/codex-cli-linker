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


def test_to_json_yaml_emit():
    cli = load_cli()
    cfg = {
        "a": 1,
        "b": True,
        "c": [1, 2, {"x": "y"}],
        "d": {"e": False, "f": ["s"]},
    }
    js = cli.to_json(cfg)
    ya = cli.to_yaml(cfg)
    assert '"a": 1' in js and '"b": true' in js
    # YAML is simplistic but should include keys and structure
    assert "a: 1" in ya and "b: true" in ya and "- 1" in ya and 'x: "y"' in ya


def test_prompt_choice_and_yes_no(monkeypatch, capsys):
    cli = load_cli()
    inputs = iter(["0", "2", "", "no", "y"])  # invalid -> valid, default->no->yes
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    idx = cli.prompt_choice("Pick", ["one", "two", "three"])
    assert idx == 1
    out = capsys.readouterr().out
    assert "Invalid choice" in out

    # default True and empty -> True
    assert cli.prompt_yes_no("Q?", default=True) is True
    # explicit no
    assert cli.prompt_yes_no("Q?", default=True) is False
    # explicit yes
    assert cli.prompt_yes_no("Q?", default=False) is True


def test_pick_base_url_variants(monkeypatch):
    cli = load_cli()
    st = cli.LinkerState(base_url="http://last:9/v1")

    # Auto branch returns detection or fallback
    monkeypatch.setattr(cli, "detect_base_url", lambda: None)
    assert cli.pick_base_url(st, auto=True) == "http://last:9/v1"

    # Interactive: choose LM Studio
    inputs = iter(["1"])  # LM Studio
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert cli.pick_base_url(st, auto=False) == cli.DEFAULT_LMSTUDIO

    # Interactive: choose Ollama
    inputs = iter(["2"])  # Ollama
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert cli.pick_base_url(st, auto=False) == cli.DEFAULT_OLLAMA

    # Interactive: custom then URL
    inputs = iter(["3", "http://custom:1/v1"])  # Custom -> URL
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert cli.pick_base_url(st, auto=False) == "http://custom:1/v1"

    # Interactive: Auto-detect with fallback prompt
    inputs = iter(["4", "http://fallback:2/v1"])  # Auto -> fallback manual URL
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(cli, "detect_base_url", lambda: None)
    assert cli.pick_base_url(st, auto=False) == "http://fallback:2/v1"

    # Interactive: Use last saved
    inputs = iter(["5"])  # last saved
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert cli.pick_base_url(st, auto=False) == "http://last:9/v1"


def test_pick_model_interactive(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "list_models", lambda base: ["m1", "m2", "m3"])
    inputs = iter(["2"])  # choose second
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    choice = cli.pick_model_interactive("http://localhost:1234/v1", last="m3")
    assert choice == "m2"


def test_list_models_error(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli, "http_get_json", lambda url: (None, "boom"))
    try:
        cli.list_models("http://x")
        assert False, "expected error"
    except RuntimeError as e:
        assert "Failed to fetch models" in str(e)


def test_try_auto_context_window(monkeypatch):
    cli = load_cli()
    # Provide metadata in different shapes to exercise extract logic
    data = {
        "data": [
            {"id": "m1", "meta": {"n_ctx": 2048}},
            {"id": "m2", "metadata": {"context_window": 4096}},
        ]
    }
    monkeypatch.setattr(cli, "http_get_json", lambda url: (data, None))
    # Exact match first entry uses meta.n_ctx
    assert cli.try_auto_context_window("http://x", "m1") == 2048
    # For unknown model id, should still find a value in the list
    assert cli.try_auto_context_window("http://x", "zzz") in (2048, 4096)


def test_ensure_codex_cli_fail_paths(monkeypatch):
    cli = load_cli()
    # No codex, no npx, no npm
    monkeypatch.setattr(cli, "find_codex_cmd", lambda: None)
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    try:
        cli.ensure_codex_cli()
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "Codex CLI is required" in str(e)

    # npm present but install fails
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: "+npm+" if name == "npm" else None
    )
    called = {"cmd": None}

    def fake_check_call(cmd):
        called["cmd"] = cmd
        raise cli.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(cli.subprocess, "check_call", fake_check_call)
    try:
        cli.ensure_codex_cli()
        assert False, "expected SystemExit"
    except SystemExit:
        pass
    assert called["cmd"] is not None and "@openai/codex-cli" in called["cmd"]

    # npm install succeeds and find_codex_cmd returns a value
    def ok_check_call(cmd):
        called["cmd"] = cmd
        return 0

    monkeypatch.setattr(cli.subprocess, "check_call", ok_check_call)
    monkeypatch.setattr(cli, "find_codex_cmd", lambda: ["npx", "codex"])
    assert cli.ensure_codex_cli() == ["npx", "codex"]


def test_find_codex_cmd_none(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert cli.find_codex_cmd() is None


def test_ui_helpers_no_crash(monkeypatch, capsys):
    cli = load_cli()
    # Force no color
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    s = cli.c("X", cli.GREEN)
    assert s == "X"  # no color applied when not tty
    cli.info("i")
    cli.ok("o")
    cli.warn("w")
    cli.err("e")
    # clear_screen and banner shouldn't raise
    cli.clear_screen()
    cli.banner()
