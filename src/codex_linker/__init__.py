import shutil
import subprocess
import sys


def main() -> int:
    """Console entrypoint that delegates to the bundled script.

    Prefer the original CLI script when available to preserve behavior.
    This keeps tests and the existing single-file UX intact while
    providing a main entrypoint for packaging.
    """
    target = shutil.which("codex-cli-linker.py")
    if target:
        try:
            return subprocess.call([sys.executable, target, *sys.argv[1:]])
        except Exception:
            pass
    # Fallback: attempt to import and run if the monolith is importable
    try:
        import importlib

        mod = importlib.import_module("codex_cli_linker")
        if hasattr(mod, "main"):
            mod.main()
            return 0
    except Exception:
        pass
    sys.stderr.write("codex-cli-linker entry not found.\n")
    return 1


__all__ = ["main"]
