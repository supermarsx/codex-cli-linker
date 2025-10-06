#!/usr/bin/env python3
"""Launcher and compatibility shim for Codex CLI Linker.

This small wrapper keeps the historical, single-file UX intact while also
supporting packaging (PyPI/Homebrew) and frozen distributions (PyInstaller).

Key behavior and rationale:
 - Prefer static imports first so that packagers like PyInstaller can detect
   and bundle the ``codex_linker`` package without additional hooks.
 - Fall back to dynamically adding ``./src`` to ``sys.path`` when running
   the repository directly (editable development mode).
 - Re-export key symbols from the implementation module to preserve backwards
   compatibility with tests and scripts that import from this file.

No third‑party dependencies are used; this file must remain stdlib‑only.
"""

import importlib
import os as _os
import sys
from pathlib import Path


def _load_modules():
    """Locate and import the packaged modules.

    Strategy:
    1) Prefer a direct import (static) so PyInstaller collectors can see the
       dependency graph and include ``codex_linker`` in the frozen app.
    2) If the import fails (e.g., when running the repo directly), add the
       local ``./src`` directory to ``sys.path`` and environment to mirror the
       project layout, then retry import via :mod:`importlib`.

    Returns a tuple of (impl_module, utils_module).
    """
    # 1) Static import first (helps PyInstaller collectors)
    try:
        from codex_linker import impl as _impl  # type: ignore
        from codex_linker import utils as _utils  # type: ignore

        return _impl, _utils
    except Exception:
        pass

    # 2) Dev/source tree fallback: add ./src to path and env
    _here = Path(__file__).resolve().parent
    _src = _here / "src"
    if _src.exists():
        src_str = str(_src)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        env_path = _os.environ.get("PYTHONPATH")
        if env_path:
            paths = env_path.split(_os.pathsep)
            if src_str not in paths:
                _os.environ["PYTHONPATH"] = _os.pathsep.join([src_str, env_path])
        else:
            _os.environ["PYTHONPATH"] = src_str

    # 3) Importlib-based import
    _impl = importlib.import_module("codex_linker.impl")
    _utils = importlib.import_module("codex_linker.utils")
    return _impl, _utils


_impl, _utils = _load_modules()

parse_args = _impl.parse_args
configure_logging = _impl.configure_logging
log_event = _impl.log_event
merge_config_defaults = _impl.merge_config_defaults
apply_saved_state = _impl.apply_saved_state
prompt_choice = _impl.prompt_choice
prompt_yes_no = _impl.prompt_yes_no
pick_base_url = _impl.pick_base_url
pick_model_interactive = _impl.pick_model_interactive
interactive_prompts = _impl.interactive_prompts
banner = _impl.banner
clear_screen = _impl.clear_screen
c = _impl.c
info = _impl.info
ok = _impl.ok
warn = _impl.warn
err = _impl.err
supports_color = _impl.supports_color
RESET = _impl.RESET
BOLD = _impl.BOLD
DIM = _impl.DIM
RED = _impl.RED
GREEN = _impl.GREEN
YELLOW = _impl.YELLOW
BLUE = _impl.BLUE
CYAN = _impl.CYAN
GRAY = _impl.GRAY
LinkerState = _impl.LinkerState
to_toml = _impl.to_toml
to_json = _impl.to_json
to_yaml = _impl.to_yaml
build_config_dict = _impl.build_config_dict
store_api_key_in_keychain = _impl.store_api_key_in_keychain
detect_base_url = _impl.detect_base_url
list_models = _impl.list_models
try_auto_context_window = _impl.try_auto_context_window
_keychain_backend_auto = _impl._keychain_backend_auto
backup = _impl.backup
DEFAULT_LMSTUDIO = _impl.DEFAULT_LMSTUDIO
DEFAULT_OLLAMA = _impl.DEFAULT_OLLAMA
DEFAULT_VLLM = _impl.DEFAULT_VLLM
DEFAULT_TGWUI = _impl.DEFAULT_TGWUI
DEFAULT_TGI_8080 = _impl.DEFAULT_TGI_8080
DEFAULT_OPENROUTER_LOCAL = _impl.DEFAULT_OPENROUTER_LOCAL
DEFAULT_OPENAI = _impl.DEFAULT_OPENAI
PROVIDER_LABELS = _impl.PROVIDER_LABELS
pkg_version = _impl.pkg_version
find_codex_cmd = _impl.find_codex_cmd
ensure_codex_cli = _impl.ensure_codex_cli
CODEX_HOME = _impl.CODEX_HOME
CONFIG_TOML = _impl.CONFIG_TOML
CONFIG_JSON = _impl.CONFIG_JSON
CONFIG_YAML = _impl.CONFIG_YAML
LINKER_JSON = _impl.LINKER_JSON
AUTH_JSON = _impl.AUTH_JSON
atomic_write_with_backup = _impl.atomic_write_with_backup
delete_all_backups = _impl.delete_all_backups
remove_config = _impl.remove_config
get_version = _impl.get_version
check_for_updates = _impl.check_for_updates
determine_update_sources = _impl.determine_update_sources
detect_install_origin = _impl.detect_install_origin
is_version_newer = _impl.is_version_newer
SourceResult = _impl.SourceResult
UpdateCheckResult = _impl.UpdateCheckResult
run_doctor = _impl.run_doctor
_log_update_sources = _impl._log_update_sources
_report_update_status = _impl._report_update_status
http_get_json = _impl.http_get_json
os = _impl.os
shutil = _impl.shutil
subprocess = _impl.subprocess
urllib = _impl.urllib
logging = _impl.logging
datetime = _impl.datetime
main = _impl.main
resolve_provider = _impl.resolve_provider

__all__ = [
    "parse_args",
    "configure_logging",
    "log_event",
    "merge_config_defaults",
    "apply_saved_state",
    "prompt_choice",
    "prompt_yes_no",
    "pick_base_url",
    "pick_model_interactive",
    "interactive_prompts",
    "banner",
    "clear_screen",
    "c",
    "info",
    "ok",
    "warn",
    "err",
    "supports_color",
    "RESET",
    "BOLD",
    "DIM",
    "RED",
    "GREEN",
    "YELLOW",
    "BLUE",
    "CYAN",
    "GRAY",
    "LinkerState",
    "to_toml",
    "to_json",
    "to_yaml",
    "build_config_dict",
    "store_api_key_in_keychain",
    "detect_base_url",
    "list_models",
    "try_auto_context_window",
    "_keychain_backend_auto",
    "backup",
    "DEFAULT_LMSTUDIO",
    "DEFAULT_OLLAMA",
    "DEFAULT_VLLM",
    "DEFAULT_TGWUI",
    "DEFAULT_TGI_8080",
    "DEFAULT_OPENROUTER_LOCAL",
    "DEFAULT_OPENAI",
    "PROVIDER_LABELS",
    "pkg_version",
    "find_codex_cmd",
    "ensure_codex_cli",
    "launch_codex",
    "CODEX_HOME",
    "CONFIG_TOML",
    "CONFIG_JSON",
    "CONFIG_YAML",
    "LINKER_JSON",
    "AUTH_JSON",
    "atomic_write_with_backup",
    "delete_all_backups",
    "remove_config",
    "get_version",
    "check_for_updates",
    "determine_update_sources",
    "detect_install_origin",
    "is_version_newer",
    "SourceResult",
    "UpdateCheckResult",
    "run_doctor",
    "_log_update_sources",
    "_report_update_status",
    "http_get_json",
    "os",
    "shutil",
    "subprocess",
    "urllib",
    "logging",
    "datetime",
    "main",
    "resolve_provider",
]


def launch_codex(profile: str) -> int:
    """Forward to utils.launch_codex using this module's ensure."""
    return _utils.launch_codex(profile, ensure_codex_cli)


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        print()
        try:
            warn("Aborted by user.")
        except Exception:
            pass
