import importlib.util
import json
import os
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


def test_set_openai_key_mode_writes_auth_json(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cli = load_cli()
    auth = tmp_path / "auth.json"
    # Patch both the main_flow binding and the underlying io_safe constant to isolate path
    import sys as _sys
    mf = _sys.modules.get("codex_linker.main_flow")
    if mf is not None:
        monkeypatch.setattr(mf, "AUTH_JSON", auth, raising=False)
    io = _sys.modules.get("codex_linker.io_safe")
    if io is not None:
        monkeypatch.setattr(io, "AUTH_JSON", auth, raising=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codex-cli-linker.py",
            "--set-openai-key",
            "--api-key",
            "sk-test-123",
        ],
    )
    cli.main()
    data = json.loads(auth.read_text(encoding="utf-8"))
    assert data.get("OPENAI_API_KEY") == "sk-test-123"


def test_provider_preset_env_headers(monkeypatch):
    cli = load_cli()
    state = cli.LinkerState()

    # Groq -> Authorization header with env var
    args = cli.parse_args(["--provider", "groq"])
    cfg = cli.build_config_dict(state, args)
    assert (
        cfg["model_providers"]["groq"]["env_http_headers"].get("Authorization")
        == "GROQ_API_KEY"
    )

    # Anthropic -> x-api-key header
    args = cli.parse_args(["--provider", "anthropic"])
    cfg = cli.build_config_dict(state, args)
    assert (
        cfg["model_providers"]["anthropic"]["env_http_headers"].get("x-api-key")
        == "ANTHROPIC_API_KEY"
    )

    # Azure -> api-key header
    args = cli.parse_args(["--provider", "azure", "--azure-api-version", "2024-05-01"])
    cfg = cli.build_config_dict(state, args)
    assert (
        cfg["model_providers"]["azure"]["env_http_headers"].get("api-key")
        == "AZURE_OPENAI_API_KEY"
    )


def test_tui_notifications_emit(monkeypatch):
    cli = load_cli()
    state = cli.LinkerState()
    args = cli.parse_args(["--tui-notifications", "--tui-notification-types", "agent-turn-complete,approval-requested"])
    cfg = cli.build_config_dict(state, args)
    assert cfg.get("tui", {}).get("notifications") == [
        "agent-turn-complete",
        "approval-requested",
    ]


def test_mcp_servers_normalization_via_json_flag(monkeypatch):
    cli = load_cli()
    state = cli.LinkerState()
    mcp_json = json.dumps(
        {
            "s1": {
                "command": "npx",
                "args": "-y, mcp-server",
                "env": {"API_KEY": "value"},
                "startup_timeout_ms": 20000,
            }
        }
    )
    args = cli.parse_args(["--mcp-json", mcp_json])
    cfg = cli.build_config_dict(state, args)
    s1 = cfg.get("mcp_servers", {}).get("s1")
    assert s1 and s1["command"] == "npx" and s1["args"] == ["-y", "mcp-server"]
    assert s1["env"].get("API_KEY") == "value" and s1.get("startup_timeout_ms") == 20000


def test_openai_auth_mode_shortcuts(monkeypatch):
    cli = load_cli()
    # API key mode
    args = cli.parse_args(["--openai-api"])  # implies provider=openai
    assert args.provider == "openai" and args.preferred_auth_method == "apikey"
    # ChatGPT mode
    args = cli.parse_args(["--openai-gpt"])  # implies provider=openai
    assert args.provider == "openai" and args.preferred_auth_method == "chatgpt"
