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


def test_keychain_backends_noop_on_wrong_platform(monkeypatch):
    cli = load_cli()

    # none backend -> False
    assert cli.store_api_key_in_keychain("none", "ENVX", "abc") is False

    # macos on non-darwin -> False
    monkeypatch.setattr(cli.sys, "platform", "win32", raising=False)
    assert cli.store_api_key_in_keychain("macos", "ENVX", "abc") is False

    # dpapi on non-Windows -> False
    monkeypatch.setattr(cli.os, "name", "posix", raising=False)
    assert cli.store_api_key_in_keychain("dpapi", "ENVX", "abc") is False

    # secretstorage missing -> False
    # Simulate ImportError path
    assert cli.store_api_key_in_keychain("secretstorage", "ENVX", "abc") is False


def test_keychain_auto_mapping(monkeypatch):
    cli = load_cli()
    monkeypatch.setattr(cli.sys, "platform", "darwin", raising=False)
    assert cli._keychain_backend_auto() == "macos"
    monkeypatch.setattr(cli.sys, "platform", "linux", raising=False)
    monkeypatch.setattr(cli.os, "name", "posix", raising=False)
    assert cli._keychain_backend_auto() == "secretstorage"
    monkeypatch.setattr(cli.os, "name", "nt", raising=False)
    assert cli._keychain_backend_auto() == "dpapi"


def test_providers_are_added_to_config():
    cli = load_cli()
    args = cli.parse_args(
        [
            "--auto",
            "--base-url",
            cli.DEFAULT_LMSTUDIO,
            "--model",
            "m1",
            "--providers",
            "lmstudio,ollama,vllm,tgi,tgwui,openrouter,jan,llamafile,gpt4all,local",
        ]
    )
    state = cli.LinkerState()
    cfg = cli.build_config_dict(state, args)
    # Check profiles present for requested providers
    profs = cfg.get("profiles", {})
    for p in [
        "lmstudio",
        "ollama",
        "vllm",
        "tgi",
        "tgwui",
        "openrouter",
        "jan",
        "llamafile",
        "gpt4all",
        "local",
    ]:
        assert p in profs
