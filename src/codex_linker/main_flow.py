from __future__ import annotations
import difflib
import os
import re
import sys
import time
from pathlib import Path
from .args import parse_args
from .config_utils import merge_config_defaults, apply_saved_state
from .prompts import pick_base_url, pick_model_interactive, interactive_prompts
from .logging_utils import configure_logging, log_event
from .render import build_config_dict
from .emit import to_toml, to_json, to_yaml
from .detect import list_models, try_auto_context_window
from .io_safe import (
    CODEX_HOME,
    atomic_write_with_backup,
    delete_all_backups,
    remove_config,
)
from .keychain import store_api_key_in_keychain
from .state import LinkerState
from .ui import banner, clear_screen, c, info, ok, warn, err, CYAN
from .utils import get_version, resolve_provider
from .updates import (
    check_for_updates,
    determine_update_sources,
    detect_install_origin,
    UpdateCheckResult,
)
from .doctor import run_doctor


def _label_source(name: str) -> str:
    mapping = {"github": "GitHub", "pypi": "PyPI"}
    return mapping.get(name.lower(), name.title())


def _label_origin(origin: str) -> str:
    mapping = {"pypi": "PyPI install", "git": "Git checkout", "binary": "packaged binary", "homebrew": "Homebrew tap", "brew": "Homebrew tap", "scoop": "Scoop install"}
    return mapping.get(origin.lower(), origin or "unknown")


def _log_update_sources(result: UpdateCheckResult, forced: bool, origin: str) -> None:
    for src in result.sources:
        log_event(
            "update_check_source",
            source=src.name,
            version=src.version or "",
            error=src.error or None,
            forced=forced,
            origin=origin,
            used_cache=result.used_cache,
        )


def _report_update_status(
    result: UpdateCheckResult,
    current_version: str,
    *,
    forced: bool,
    verbose: bool,
    origin: str,
) -> None:
    origin_label = _label_origin(origin)
    sources_label = ", ".join(_label_source(src.name) for src in result.sources)
    if forced:
        info(f"Current version: {current_version}")
    if (forced or verbose) and sources_label:
        info(f"Detected {origin_label}; checking {sources_label} for updates.")
    elif (forced or verbose) and not sources_label:
        warn(f"No update sources configured for origin '{origin}'.")
    all_failed = len(result.errors) == len(result.sources)
    if forced or verbose or result.has_newer or all_failed:
        for src in result.sources:
            label = _label_source(src.name)
            if src.version:
                info(f"{label} latest: {src.version}")
                if (forced or result.has_newer) and src.url:
                    info(f"{label} release: {src.url}")
            if src.error and (forced or verbose or all_failed):
                warn(f"{label} check error: {src.error}")
    if result.has_newer:
        summary = ", ".join(
            f"{_label_source(src.name)} {src.version}"
            for src in result.newer_sources
            if src.version
        )
        if summary:
            warn(f"Update available ({summary}); current version is {current_version}.")
        else:
            warn(f"Update available; current version is {current_version}.")
    elif forced or (verbose and not result.errors):
        ok("codex-cli-linker is up to date.")




def main():
    """Entry point for the CLI tool."""
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
    log_event("update_origin_detected", origin=install_origin, sources=",".join(update_sources))
    sources_arg = update_sources or None
    if getattr(args, "check_updates", False):
        try:
            result = check_for_updates(current_version, home, force=True, sources=sources_arg)
        except Exception as exc:
            warn(f"Update check failed: {exc}")
            log_event("update_check_failed", forced=True, origin=install_origin, error=str(exc))
            return
        _log_update_sources(result, forced=True, origin=install_origin)
        _report_update_status(result, current_version, forced=True, verbose=True, origin=install_origin)
        log_event("update_check_completed", forced=True, origin=install_origin, newer=result.has_newer, used_cache=result.used_cache, sources=",".join(update_sources))
        return
    if getattr(args, "version", False):
        print(current_version)
        return
    # Trim banners on non-TTY or when NO_COLOR is set
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    should_clear = (
        is_tty
        and not os.environ.get("NO_COLOR")
        and (os.name != "nt" or getattr(args, "clear", False))
    )
    if should_clear:
        clear_screen()
        banner()
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
    # Hard-disable auto launch regardless of flags
    args.launch = False
    # Determine state file path
    state_file_override = getattr(args, "state_file", None)
    workspace_state_path = Path.cwd() / ".codex-linker.json"
    use_workspace_state = getattr(args, "workspace_state", False)
    if state_file_override:
        state_path = Path(state_file_override)
    else:
        if not use_workspace_state and workspace_state_path.exists():
            use_workspace_state = True
        state_path = workspace_state_path if use_workspace_state else linker_json
    state = LinkerState.load(state_path)
    log_event(
        "state_path_selected",
        path=str(state_path),
        workspace=bool(use_workspace_state),
        override=bool(state_file_override),
    )
    apply_saved_state(args, defaults, state)

    if getattr(args, "doctor", False):
        targets = [config_toml]
        if args.json:
            targets.append(config_json)
        if args.yaml:
            targets.append(config_yaml)
        exit_code = run_doctor(args, home, targets, state=state)
        sys.exit(exit_code)

    if not getattr(args, "no_update_check", False):
        try:
            update_result = check_for_updates(current_version, home, sources=sources_arg)
        except Exception as exc:
            log_event("update_check_failed", forced=False, origin=install_origin, error=str(exc))
            if args.verbose:
                warn(f"Update check failed: {exc}")
        else:
            _log_update_sources(update_result, forced=False, origin=install_origin)
            _report_update_status(update_result, current_version, forced=False, verbose=args.verbose, origin=install_origin)
            log_event("update_check_completed", forced=False, origin=install_origin, newer=update_result.has_newer, used_cache=update_result.used_cache, sources=",".join(update_sources))

    # Base URL: auto-detect or prompt
    picker = getattr(
        sys.modules.get("codex_cli_linker"), "pick_base_url", pick_base_url
    )
    if args.auto:
        base = args.base_url or picker(state, True)
    else:
        if getattr(args, "yes", False) and not args.base_url:
            err("--yes provided but no --base-url; refusing to prompt.")
            sys.exit(2)
        base = args.base_url or picker(state, False)
    state.base_url = base

    # Infer a safe default provider from the base URL (localhost:1234 → lmstudio, 11434 → ollama, otherwise 'custom').
    default_provider = resolve_provider(base)
    state.provider = args.provider or default_provider
    if state.provider == "custom":
        state.provider = (
            input("Provider id to use in model_providers (e.g., myprovider): ").strip()
            or "custom"
        )

    state.profile = args.profile or state.profile or state.provider
    state.api_key = args.api_key or state.api_key or "sk-local"
    # Optional: store provided API key in OS keychain (never required)
    if args.api_key and args.keychain and args.keychain != "none":
        success = store_api_key_in_keychain(args.keychain, state.env_key, args.api_key)
        log_event(
            "keychain_store",
            provider=state.provider,
            path=state.env_key,
            error_type=None if success else "store_failed",
        )
    if "env_key_name" in getattr(args, "_explicit", set()):
        state.env_key = args.env_key_name
    else:
        state.env_key = (
            state.env_key or "NULLKEY"
        )  # pragma: no cover (default path exercised via state)

    # Model selection: interactive unless provided
    if args.model:
        target = args.model
        chosen = target
        try:
            lm = getattr(
                sys.modules.get("codex_cli_linker"), "list_models", list_models
            )
            models = lm(state.base_url)
            if target in models:
                chosen = target
            else:
                t = target.lower()
                matches = sorted([m for m in models if t in m.lower()])
                if matches:
                    chosen = matches[0]
                    ok(f"Selected model by substring match: {chosen}")
        except Exception:
            pass
        state.model = chosen
        log_event("model_selected", provider=state.provider, model=state.model)
    elif args.auto and args.model_index is not None:
        try:
            lm = getattr(
                sys.modules.get("codex_cli_linker"), "list_models", list_models
            )
            models = lm(state.base_url)
            idx = args.model_index if args.model_index >= 0 else 0
            if idx >= len(models):
                idx = 0
            state.model = models[idx]
            ok(f"Auto-selected model: {state.model}")
            log_event("model_selected", provider=state.provider, model=state.model)
        except Exception as e:
            err(str(e))
            sys.exit(2)
    else:
        if getattr(args, "yes", False):
            err(
                "--yes provided but no model specified; use --model or --model-index with --auto."
            )
            sys.exit(2)
        try:
            state.model = pick_model_interactive(state.base_url, state.model or None)
        except Exception as e:
            err(str(e))
            sys.exit(2)

    if not args.auto:
        interactive_prompts(args)

    state.approval_policy = args.approval_policy
    state.sandbox_mode = args.sandbox_mode
    state.reasoning_effort = args.reasoning_effort
    state.reasoning_summary = args.reasoning_summary
    state.verbosity = args.verbosity
    state.disable_response_storage = args.disable_response_storage
    state.no_history = args.no_history
    state.history_max_bytes = args.history_max_bytes

    # Auto-detect context window if not provided
    if (args.model_context_window or 0) <= 0:
        try:
            tacw = getattr(
                sys.modules.get("codex_cli_linker"),
                "try_auto_context_window",
                try_auto_context_window,
            )
            cw = tacw(state.base_url, state.model)
            if cw > 0:
                ok(f"Detected context window: {cw} tokens")
                args.model_context_window = cw
            else:
                warn("Could not detect context window; leaving as 0.")
        except Exception as _e:
            warn(f"Context window detection failed: {_e}")

    # Build config dict per spec
    cfg = build_config_dict(state, args)

    # Prepare TOML output (and optionally JSON/YAML)
    toml_out = to_toml(cfg)
    toml_out = re.sub(r"\n{3,}", "\n\n", toml_out).rstrip() + "\n"

    if args.dry_run:
        if getattr(args, "diff", False):
            # Show diffs versus existing files
            def show_diff(path: Path, new_text: str, label: str):
                try:
                    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
                except Exception:
                    old_text = ""
                diff = difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=f"{label} (proposed)",
                )
                sys.stdout.writelines(diff)

            show_diff(config_toml, toml_out, "config.toml")
            if args.json:
                show_diff(config_json, to_json(cfg), "config.json")
            if args.yaml:
                show_diff(config_yaml, to_yaml(cfg), "config.yaml")
        else:
            print(toml_out, end="")
            if args.json:
                print(to_json(cfg))
            if args.yaml:
                print(to_yaml(cfg))
        info("Dry run: no files were written.")
    else:
        # Ensure home dir exists
        home.mkdir(parents=True, exist_ok=True)

        # Always write TOML; JSON/YAML only if flags requested. Normalize blank lines and ensure trailing newline.
        t0 = time.time()
        atomic_write_with_backup(config_toml, toml_out)
        log_event(
            "write_config",
            provider=state.provider,
            model=state.model,
            path=str(config_toml),
            duration_ms=int((time.time() - t0) * 1000),
        )
        ok(f"Wrote {config_toml}")

        if args.json:
            t1 = time.time()
            atomic_write_with_backup(config_json, to_json(cfg))
            log_event(
                "write_config",
                provider=state.provider,
                model=state.model,
                path=str(config_json),
                duration_ms=int((time.time() - t1) * 1000),
            )
            ok(f"Wrote {config_json}")

        if args.yaml:
            t2 = time.time()
            atomic_write_with_backup(config_yaml, to_yaml(cfg))
            log_event(
                "write_config",
                provider=state.provider,
                model=state.model,
                path=str(config_yaml),
                duration_ms=int((time.time() - t2) * 1000),
            )
            ok(f"Wrote {config_yaml}")

        # Save linker state for next run (no secrets)
        state.save(state_path)

    # Friendly summary and manual run hint
    print()
    ok(
        f"Configured profile '{state.profile}' using provider '{state.provider}' → {state.base_url} (model: {state.model})"
    )
    # Post-run report
    info("Summary:")
    print(c(f"  target: {config_toml}", CYAN))
    try:
        last_bak = max(config_toml.parent.glob("config.toml.*.bak"), default=None)
    except Exception:
        last_bak = None
    if last_bak:
        print(c(f"  backup: {last_bak}", CYAN))
    print(c(f"  profile: {state.profile}", CYAN))
    print(c(f"  provider: {state.provider}", CYAN))
    print(c(f"  model: {state.model}", CYAN))
    print(c(f"  context_window: {args.model_context_window or 0}", CYAN))
    print(c(f"  max_output_tokens: {args.model_max_output_tokens or 0}", CYAN))
    info("Run Codex manually with:")
    print(c(f"  npx codex --profile {state.profile}", CYAN))
    print(c(f"  codex --profile {state.profile}", CYAN))

    # Optional: suggest an editor command to open the generated config
    if getattr(args, "open_config", False):
        opener = (args.file_opener or "vscode").strip().lower()
        if opener == "vscode-insiders":
            cmd = f'code-insiders "{config_toml}"'
        else:
            cmd = f'code "{config_toml}"'
        info("Open config in your editor:")
        print(c(f"  {cmd}", CYAN))


__all__ = ["main"]
