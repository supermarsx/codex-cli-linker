from __future__ import annotations

import datetime
import logging
import os
import shutil
import subprocess
import sys
import urllib

from .args import parse_args
from .logging_utils import configure_logging, log_event
from .config_utils import merge_config_defaults, apply_saved_state
from .prompts import (
    prompt_choice,
    prompt_yes_no,
    pick_base_url,
    pick_model_interactive,
    interactive_prompts,
)
from .render import build_config_dict
from .emit import to_toml, to_json, to_yaml
from .state import LinkerState
from .ui import (
    banner,
    clear_screen,
    c,
    info,
    ok,
    warn,
    err,
    supports_color,
    RESET,
    BOLD,
    DIM,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    CYAN,
    GRAY,
)
from .keychain import store_api_key_in_keychain, _keychain_backend_auto
from .detect import detect_base_url, list_models, try_auto_context_window
from .spec import (
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
    DEFAULT_OPENAI,
    PROVIDER_LABELS,
)
from .io_safe import (
    CODEX_HOME,
    CONFIG_TOML,
    CONFIG_JSON,
    CONFIG_YAML,
    LINKER_JSON,
    AUTH_JSON,
    atomic_write_with_backup,
    delete_all_backups,
    remove_config,
    backup,
)
from .utils import (
    get_version,
    http_get_json,
    pkg_version,
    find_codex_cmd,
    ensure_codex_cli,
    launch_codex,
    resolve_provider,
)
from .updates import (
    check_for_updates,
    determine_update_sources,
    detect_install_origin,
    is_version_newer,
    SourceResult,
    UpdateCheckResult,
)
from .main_flow import main, _log_update_sources, _report_update_status


def run_doctor(*args, **kwargs):
    """Proxy to :mod:`codex_linker.doctor` that tolerates module reloads."""

    module = sys.modules.get("codex_linker.doctor")
    if module is None:
        from . import doctor as module  # type: ignore[no-redef]

    return module.run_doctor(*args, **kwargs)


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
    "DEFAULT_TGI_3000",
    "DEFAULT_OPENAI",
    "DEFAULT_OPENROUTER_LOCAL",
    "PROVIDER_LABELS",
    "pkg_version",
    "find_codex_cmd",
    "ensure_codex_cli",
    "launch_codex",
    "resolve_provider",
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
]
