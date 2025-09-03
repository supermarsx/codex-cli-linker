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


def test_env_key_name_in_config():
    cli = load_cli()
    args = cli.parse_args(["--env-key-name", "MYKEY"])
    state = cli.LinkerState()
    if "env_key_name" in getattr(args, "_explicit", set()):
        state.env_key = args.env_key_name
    cfg = cli.build_config_dict(state, args)
    assert state.env_key == "MYKEY"
    assert cfg["model_providers"][state.provider]["api_key_env_var"] == "MYKEY"
