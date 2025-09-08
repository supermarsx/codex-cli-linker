from pathlib import Path
import sys


def load_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
    )
    cli = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    return cli


def test_to_toml_comprehensive_sections():
    cli = load_cli()
    cfg = {
        "model": "mX",
        "model_provider": "provX",
        "approval_policy": "on-failure",
        "sandbox_mode": "workspace-write",
        "file_opener": "vscode",
        "tools": {"web_search": True},
        "history": {"persistence": "save-all", "max_bytes": 2048},
        "sandbox_workspace_write": {
            "writable_roots": ["/data"],
            "network_access": True,
            "exclude_tmpdir_env_var": False,
            "exclude_slash_tmp": True,
        },
        "profile": "pX",
        "disable_response_storage": False,
        "model_reasoning_effort": "low",
        "model_reasoning_summary": "auto",
        "model_verbosity": "medium",
        "model_context_window": 256,
        "model_max_output_tokens": 128,
        "project_doc_max_bytes": 1024,
        "tui": "table",
        "hide_agent_reasoning": False,
        "show_raw_agent_reasoning": True,
        "model_supports_reasoning_summaries": False,
        "chatgpt_base_url": "",
        "experimental_resume": "",
        "experimental_instructions_file": "",
        "experimental_use_exec_command_tool": False,
        "responses_originator_header_internal_override": "",
        "preferred_auth_method": "apikey",
        "model_providers": {
            "provX": {
                "name": "Prov X",
                "base_url": "http://localhost:1/v1",
                "wire_api": "chat",
                "api_key_env_var": "NULLKEY",
                "request_max_retries": 2,
                "stream_max_retries": 3,
                "stream_idle_timeout_ms": 100,
                "query_params": {"api-version": "2024-05-01"},
            },
            "provY": {
                "name": "Prov Y",
                "base_url": "http://localhost:2/v1",
                "wire_api": "chat",
                "api_key_env_var": "NULLKEY",
                "request_max_retries": 1,
                "stream_max_retries": 1,
                "stream_idle_timeout_ms": 1,
            },
        },
        "profiles": {
            "pX": {
                "model": "mX",
                "model_provider": "provX",
                "model_context_window": 256,
                "model_max_output_tokens": 128,
                "approval_policy": "on-failure",
            },
            "pY": {
                "model": "mY",
                "model_provider": "provY",
            },
        },
    }
    t = cli.to_toml(cfg)
    # Core sections
    assert "[tools]" in t and "web_search = true" in t
    assert "[history]" in t and "max_bytes = 2048" in t
    assert (
        "[sandbox_workspace_write]" in t
        and "writable_roots" in t
        and "network_access = true" in t
    )
    # Providers
    assert "[model_providers.provX]" in t and "[model_providers.provY]" in t
    assert "query_params = {" in t or "api-version" in t
    # Profiles
    assert "[profiles.pX]" in t and "[profiles.pY]" in t
    # JSON/YAML writers at least serialize something coherent
    js = cli.to_json(cfg)
    ya = cli.to_yaml(cfg)
    assert '"model": "mX"' in js and ('model: "mX"' in ya or "model: mX" in ya)
