import sys
from types import ModuleType


def load_pkg_init():
    # Import the installed package from src via normal import hooks
    import importlib

    return importlib.import_module("codex_linker")


def test_pkg_main_uses_shim_when_available(monkeypatch):
    pkg = load_pkg_init()
    # Make shutil.which return a dummy path
    monkeypatch.setattr(pkg, "shutil", pkg.shutil)
    monkeypatch.setattr(pkg.shutil, "which", lambda name: "/tmp/codex-cli-linker.py")
    # Monkeypatch subprocess.call to avoid executing
    called = {}

    def fake_call(argv):
        called["args"] = argv
        return 123

    monkeypatch.setattr(pkg.subprocess, "call", fake_call)
    rc = pkg.main()
    assert rc == 123
    assert called["args"][0] == sys.executable


def test_pkg_main_import_fallback(monkeypatch):
    pkg = load_pkg_init()
    # Force which to return None
    monkeypatch.setattr(pkg.shutil, "which", lambda name: None)
    # Provide a fake codex_cli_linker module with a main()
    fake = ModuleType("codex_cli_linker")

    ran = {}

    def fake_main():
        ran["ok"] = True

    fake.main = fake_main  # type: ignore[attr-defined]
    sys.modules["codex_cli_linker"] = fake
    rc = pkg.main()
    assert rc == 0 and ran.get("ok")


def test_pkg_main_error(monkeypatch, capsys):
    pkg = load_pkg_init()
    # Force which to return None and remove any importable fallback
    monkeypatch.setattr(pkg.shutil, "which", lambda name: None)
    sys.modules.pop("codex_cli_linker", None)
    rc = pkg.main()
    err = capsys.readouterr().err
    assert rc == 1 and "entry not found" in err


def test_cli_facade_exports():
    # Ensure cli facade exposes impl.main symbol
    import importlib

    impl = importlib.import_module("codex_linker.impl")
    cli = importlib.import_module("codex_linker.cli")
    assert cli.main is impl.main
