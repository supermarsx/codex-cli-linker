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
