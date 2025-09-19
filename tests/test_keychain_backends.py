import importlib
import sys
from types import SimpleNamespace
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


def test_keychain_macos_success_and_wrong_platform(monkeypatch):
    cli = load_cli()
    keychain = importlib.import_module("codex_linker.keychain")
    # Simulate macOS success
    monkeypatch.setattr(keychain.sys, "platform", "darwin")

    class R:
        def __init__(self, returncode=0):
            self.returncode = returncode

    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: R())
    assert keychain.store_api_key_in_keychain("macos", "ENV", "KEY") is True
    # Wrong platform -> skip
    monkeypatch.setattr(keychain.sys, "platform", "linux")
    assert keychain.store_api_key_in_keychain("macos", "ENV", "KEY") is False


def test_keychain_secretstorage_success_and_missing(monkeypatch):
    cli = load_cli()
    keychain = importlib.import_module("codex_linker.keychain")
    # Fake secretstorage module
    created = {}

    class Coll:
        def is_locked(self):
            return True

        def unlock(self):
            created["unlocked"] = True

        def create_item(self, label, attrs, secret, replace):
            created["item"] = (label, attrs.get("account"), secret, replace)

    fake_ss = SimpleNamespace(
        dbus_init=lambda: object(),
        get_default_collection=lambda bus: Coll(),
    )
    sys.modules["secretstorage"] = fake_ss
    assert keychain.store_api_key_in_keychain("secretstorage", "ENV", "KEY") is True
    assert created["item"][1] == "ENV"
    # Remove module -> returns False
    sys.modules.pop("secretstorage", None)
    assert keychain.store_api_key_in_keychain("secretstorage", "ENV", "KEY") is False


def test_keychain_dpapi_success_and_failure(monkeypatch):
    cli = load_cli()
    keychain = importlib.import_module("codex_linker.keychain")
    # Pretend Windows
    from types import SimpleNamespace as _NS
    monkeypatch.setattr(keychain, "os", _NS(name="nt"), raising=False)

    class CredWrite:
        def __init__(self, ok=True):
            self.ok = ok
            self.argtypes = None
            self.restype = None

        def __call__(self, *a, **k):
            return self.ok

    class Advapi:
        def __init__(self, ok=True):
            self.CredWriteW = CredWrite(ok)

    class Windll:
        def __init__(self, ok=True):
            self.advapi32 = Advapi(ok)

    # Inject fake ctypes.windll
    import ctypes as real_ctypes

    monkeypatch.setattr(keychain, "ctypes", real_ctypes, raising=False)
    monkeypatch.setattr(real_ctypes, "windll", Windll(ok=True), raising=False)
    assert keychain.store_api_key_in_keychain("dpapi", "ENV", "KEY") is True
    # Failure path when CredWriteW returns False
    monkeypatch.setattr(real_ctypes, "windll", Windll(ok=False), raising=False)
    assert keychain.store_api_key_in_keychain("dpapi", "ENV", "KEY") is False
    # Non-Windows -> skip
    monkeypatch.setattr(keychain, "os", _NS(name="posix"), raising=False)
    assert keychain.store_api_key_in_keychain("dpapi", "ENV", "KEY") is False


def test_keychain_auto_backend(monkeypatch):
    keychain = importlib.import_module("codex_linker.keychain")
    monkeypatch.setattr(keychain.sys, "platform", "darwin")
    assert keychain._keychain_backend_auto() == "macos"
    monkeypatch.setattr(keychain.sys, "platform", "linux")
    from types import SimpleNamespace as _NS
    monkeypatch.setattr(keychain, "os", _NS(name="nt"), raising=False)
    assert keychain._keychain_backend_auto() == "dpapi"
    monkeypatch.setattr(keychain, "os", _NS(name="posix"), raising=False)
    assert keychain._keychain_backend_auto() == "secretstorage"
