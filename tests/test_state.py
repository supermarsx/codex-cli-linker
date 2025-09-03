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


def test_state_round_trip(tmp_path):
    cli = load_cli()
    path = tmp_path / "linker_config.json"
    state_in = cli.LinkerState(
        base_url="http://example/v1",
        provider="custom",
        profile="test",
        api_key="k",
        env_key="E",
        model="m",
        approval_policy="untrusted",
        sandbox_mode="read-only",
        reasoning_effort="minimal",
        reasoning_summary="concise",
        verbosity="low",
        disable_response_storage=True,
        no_history=True,
        history_max_bytes=123,
    )
    state_in.save(path)
    state_out = cli.LinkerState.load(path)
    assert state_out == state_in


def test_explicit_defaults_override_saved_state():
    cli = load_cli()
    defaults = cli.parse_args([])
    state = cli.LinkerState(
        approval_policy="untrusted",
        disable_response_storage=True,
        no_history=True,
        history_max_bytes=42,
    )

    # Omitted args pick up saved state
    args = cli.parse_args([])
    cli.apply_saved_state(args, defaults, state)
    assert args.approval_policy == "untrusted"
    assert args.disable_response_storage is True
    assert args.no_history is True
    assert args.history_max_bytes == 42

    # Explicit defaults override saved state
    args = cli.parse_args(
        [
            "--approval-policy",
            "on-failure",
            "--enable-response-storage",
            "--history",
            "--history-max-bytes",
            "0",
        ]
    )
    cli.apply_saved_state(args, defaults, state)
    assert args.approval_policy == "on-failure"
    assert args.disable_response_storage is False
    assert args.no_history is False
    assert args.history_max_bytes == 0
