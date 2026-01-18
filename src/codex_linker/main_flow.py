"""Top-level CLI flow orchestration.

This module contains the primary entrypoint that wires together argument
parsing, early exits, optional migrations and update checks, interactive flows,
config shaping, and output writing. It intentionally delegates to small helper
modules (under ``flows/`` and ``prompts/``) to keep responsibilities clear and
testable while preserving the original single‑binary UX.

Key principles
- Minimal surprises at startup (no duplicate banners; respect ``--yes`` and
  non‑interactive flags).
- No third‑party dependencies; keep logic portable.
- Fail soft where possible (e.g., migrations), but exit with clear messages
  when user intent requires it (e.g., missing API key for explicit mode).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .args import parse_args
from .config_utils import merge_config_defaults, apply_saved_state
from .logging_utils import configure_logging, log_event
from .render import build_config_dict
from .emit import to_toml
from .io_safe import (
    CODEX_HOME,
    AUTH_JSON,
    atomic_write_with_backup,
    delete_all_backups,
    remove_config,
)
from .state import LinkerState
from .ui import (
    clear_screen,
    info,
    ok,
    warn,
    err,
)
from .utils import get_version
from .updates import (
    check_for_updates,
    determine_update_sources,
    detect_install_origin,
)
from .updates import _log_update_sources, _report_update_status
from .doctor import run_doctor
from .migrate import migrate_configs_to_linker
from .output_writer import handle_outputs
from .flows import (
    handle_early_exits,
    maybe_run_update_check,
    select_state_path,
    determine_base_and_provider,
    maybe_prompt_openai_auth_method,
    set_profile_and_api_key,
    maybe_prompt_and_store_openai_key,
    choose_model,
    maybe_detect_context_window,
    print_summary_and_hints,
    maybe_run_interactive_editor,
    maybe_post_editor_management,
)


# _log_update_sources and _report_update_status are imported from updates_helpers


def main():
    """Entry point for the CLI tool.

    High-level sequence
    1) Parse args, normalize convenience flags (``--auto``, ``--full-auto``),
       and configure logging.
    2) Handle early exits (``--version``, ``--check-updates``, remove/backup ops).
    3) Opportunistically migrate legacy configs into ``linker_config.json``.
    4) Doctor mode (optional), background update check.
    5) Resolve base URL and provider, auth mode, profile + key defaults.
    6) Optional guided pipeline and/or interactive editor hub.
    7) Model selection, context window detection.
    8) Shape the config dict and write outputs (TOML/JSON/YAML), then save state.
    9) Print a concise summary and hints.

    Startup output remains minimal; the interactive hub owns banner display and
    ensures a single banner per session. Non‑interactive paths (``--yes``,
    ``--dry-run``) skip prompts.
    """
    args = parse_args()
    mod = sys.modules.get("codex_cli_linker")
    home = Path(os.environ.get("CODEX_HOME", str(CODEX_HOME)))
    if "CODEX_HOME" in os.environ:
        config_toml = home / "config.toml"
        config_json = home / "config.json"
        config_yaml = home / "config.yaml"
        linker_json = home / "linker_config.json"
    else:
        config_toml = Path(getattr(mod, "CONFIG_TOML", home / "config.toml"))
        config_json = Path(getattr(mod, "CONFIG_JSON", home / "config.json"))
        config_yaml = Path(getattr(mod, "CONFIG_YAML", home / "config.yaml"))
        linker_json = Path(getattr(mod, "LINKER_JSON", home / "linker_config.json"))
    if getattr(args, "remove_config", False) or getattr(
        args, "remove_config_no_bak", False
    ):
        remove_config(getattr(args, "remove_config_no_bak", False))
        return
    if args.delete_all_backups:
        delete_all_backups(args.confirm_delete_backups)
        return
    current_version = get_version()
    install_origin = detect_install_origin()
    update_sources = determine_update_sources(install_origin)
    log_event(
        "update_origin_detected",
        origin=install_origin,
        sources=",".join(update_sources),
    )
    # sources_arg no longer needed; update_sources passed directly
    # Early exits / forced update check / version
    if handle_early_exits(
        args,
        home,
        config_targets=[config_toml, config_json, config_yaml],
        current_version=current_version,
        install_origin=install_origin,
        update_sources=update_sources,
        log_cb=_log_update_sources,
        report_cb=_report_update_status,
        log_fn=log_event,
        warn_fn=warn,
        check_fn=check_for_updates,
    ):
        return
    # Consolidate legacy config files into linker_config.json early
    # Skip during --dry-run and when using --workspace-state
    if not getattr(args, "dry_run", False) and not getattr(
        args, "workspace_state", False
    ):
        try:
            migrate_configs_to_linker(
                linker_json,
                config_toml=config_toml,
                config_json=config_json,
                config_yaml=config_yaml,
            )
        except Exception:
            # Non-fatal: continue without blocking user flow
            pass
    # Startup: banner is handled by the interactive hub; avoid extra heading here
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    color_ok = not os.environ.get("NO_COLOR")
    should_clear = (
        is_tty and color_ok and (os.name != "nt" or getattr(args, "clear", False))
    )
    if should_clear:
        clear_screen()
    # --yes implies non-interactive where possible
    if getattr(args, "yes", False):
        if not args.auto:
            args.auto = True
        if args.model_index is None and not args.model:
            args.model_index = 0
    if args.full_auto:
        args.auto = True
        if args.model_index is None:
            args.model_index = 0
    configure_logging(
        args.verbose, args.log_file, args.log_json, args.log_remote, args.log_level
    )
    defaults = parse_args([])
    merge_config_defaults(args, defaults)

    # Unique mode: only set OPENAI_API_KEY and exit
    if getattr(args, "set_openai_key", False):
        import getpass
        import json

        key_val = args.api_key or ""
        if not key_val:
            try:
                key_val = getpass.getpass(
                    "Enter OPENAI_API_KEY (input hidden): "
                ).strip()
            except Exception as exc:  # pragma: no cover
                err(f"Could not read input: {exc}")
                sys.exit(2)
        if not key_val:
            err("No API key provided; aborting.")
            sys.exit(2)

        # Ensure CODEX_HOME exists and write ~/.codex/auth.json with OPENAI_API_KEY
        home.mkdir(parents=True, exist_ok=True)
        current: dict = {}
        if AUTH_JSON.exists():
            try:
                current = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
                if not isinstance(current, dict):
                    current = {}
            except Exception:
                current = {}
        current["OPENAI_API_KEY"] = key_val

        text = json.dumps(current, indent=2) + "\n"
        atomic_write_with_backup(AUTH_JSON, text)
        log_event("openai_key_only", path=str(AUTH_JSON), stored=True)
        ok(f"Updated {AUTH_JSON} with OPENAI_API_KEY")
        warn("Never commit this file; it contains a secret.")
        return
    # Hard-disable auto launch regardless of flags
    args.launch = False
    # Determine and load state
    state_path, use_workspace_state = select_state_path(args, home, linker_json)
    state = LinkerState.load(state_path)
    apply_saved_state(args, defaults, state)

    if getattr(args, "doctor", False):
        targets = [config_toml]
        if args.json:
            targets.append(config_json)
        if args.yaml:
            targets.append(config_yaml)
        exit_code = run_doctor(args, home, targets, state=state)
        sys.exit(exit_code)

    # Background update check
    maybe_run_update_check(
        args,
        home,
        current_version=current_version,
        install_origin=install_origin,
        update_sources=update_sources,
        log_cb=_log_update_sources,
        report_cb=_report_update_status,
    )

    # Provider/base selection
    determine_base_and_provider(args, state)

    # OpenAI auth choice, when applicable
    maybe_prompt_openai_auth_method(args, state)

    # Profile and key setup
    set_profile_and_api_key(args, state)

    # In interactive OpenAI API-key mode, offer to set/update OPENAI_API_KEY in auth.json
    # OpenAI API key prompt (interactive, when applicable)
    maybe_prompt_and_store_openai_key(args, home)

    # Offer unified interactive editor unless full-auto is requested
    # Optional: jump straight into guided pipeline
    if getattr(args, "guided", False):
        try:
            from .guided_pipeline import run_guided_pipeline

            run_guided_pipeline(state, args)
            if getattr(args, "_guided_abort", False):
                info("Aborted without writing.")
                return
        except Exception as e:
            err(str(e))
            sys.exit(2)

    # Optional interactive editor/hub
    try:
        maybe_run_interactive_editor(state, args)
    except SystemExit as _e:
        # Editor requested terminate (quit/abort) gracefully
        return
    # Model selection
    choose_model(args, state)

    maybe_post_editor_management(args)

    state.approval_policy = args.approval_policy
    state.sandbox_mode = args.sandbox_mode
    state.reasoning_effort = args.reasoning_effort
    state.reasoning_summary = args.reasoning_summary
    state.verbosity = args.verbosity
    state.disable_response_storage = args.disable_response_storage
    state.no_history = args.no_history
    state.history_max_bytes = args.history_max_bytes

    # Auto-detect context window if not provided
    maybe_detect_context_window(args, state)

    # Build config dict per spec
    cfg = build_config_dict(state, args)

    # Prepare TOML output (and optionally JSON/YAML)
    toml_out = to_toml(cfg)
    toml_out = re.sub(r"\n{3,}", "\n\n", toml_out).rstrip() + "\n"

    # New unified output path: handle diffs/merges/writes in one place
    handle_outputs(
        args,
        cfg,
        toml_out,
        config_toml=config_toml,
        config_json=config_json,
        config_yaml=config_yaml,
        home=home,
        state_profile=(args.profile or state.profile or state.provider),
    )
    # Save linker state for next run (no secrets) unless dry-run
    if not getattr(args, "dry_run", False):
        state.save(state_path)

    # (legacy inline diff/merge/write flow removed; handled by handle_outputs)

    # Friendly summary and hints
    print_summary_and_hints(args, state, config_toml=config_toml)


__all__ = ["main"]
