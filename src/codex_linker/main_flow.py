from __future__ import annotations
import difflib
import os
import re
import sys
import time
from pathlib import Path
from .args import parse_args
from .config_utils import merge_config_defaults, apply_saved_state
from .prompts import (
    pick_base_url,
    pick_model_interactive,
    interactive_settings_editor,
    manage_profiles_interactive,
    manage_mcp_servers_interactive,
    prompt_choice,
    prompt_yes_no,
)
from .logging_utils import configure_logging, log_event
from .render import build_config_dict
from .emit import to_toml, to_json, to_yaml
from .detect import list_models, try_auto_context_window
from .io_safe import (
    CODEX_HOME,
    AUTH_JSON,
    atomic_write_with_backup,
    write_auth_json_merge,
    delete_all_backups,
    remove_config,
)
from .keychain import store_api_key_in_keychain
from .state import LinkerState
from .ui import (
    banner,
    clear_screen,
    c,
    info,
    ok,
    warn,
    err,
    CYAN,
    RED,
    GREEN,
    GRAY,
    supports_color,
    BOLD,
)
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
    mapping = {
        "pypi": "PyPI install",
        "git": "Git checkout",
        "binary": "packaged binary",
        "homebrew": "Homebrew tap",
        "brew": "Homebrew tap",
        "scoop": "Scoop install",
    }
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
    log_event(
        "update_origin_detected",
        origin=install_origin,
        sources=",".join(update_sources),
    )
    sources_arg = update_sources or None
    if getattr(args, "check_updates", False):
        try:
            result = check_for_updates(
                current_version, home, force=True, sources=sources_arg
            )
        except Exception as exc:
            warn(f"Update check failed: {exc}")
            log_event(
                "update_check_failed",
                forced=True,
                origin=install_origin,
                error=str(exc),
            )
            return
        _log_update_sources(result, forced=True, origin=install_origin)
        _report_update_status(
            result, current_version, forced=True, verbose=True, origin=install_origin
        )
        log_event(
            "update_check_completed",
            forced=True,
            origin=install_origin,
            newer=result.has_newer,
            used_cache=result.used_cache,
            sources=",".join(update_sources),
        )
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
    else:
        # Always present app title when launching
        print(c("CODEX CLI LINKER", CYAN))
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
            update_result = check_for_updates(
                current_version, home, sources=sources_arg
            )
        except Exception as exc:
            log_event(
                "update_check_failed",
                forced=False,
                origin=install_origin,
                error=str(exc),
            )
            if args.verbose:
                warn(f"Update check failed: {exc}")
        else:
            _log_update_sources(update_result, forced=False, origin=install_origin)
            _report_update_status(
                update_result,
                current_version,
                forced=False,
                verbose=args.verbose,
                origin=install_origin,
            )
            log_event(
                "update_check_completed",
                forced=False,
                origin=install_origin,
                newer=update_result.has_newer,
                used_cache=update_result.used_cache,
                sources=",".join(update_sources),
            )

    # Base URL: Only run old pipeline for --full-auto. Otherwise defer to editor.
    picker = getattr(
        sys.modules.get("codex_cli_linker"), "pick_base_url", pick_base_url
    )
    preferred_provider = (args.provider or "").strip().lower()
    if args.full_auto:
        if preferred_provider == "openai" and not args.base_url:
            from .spec import DEFAULT_OPENAI

            base = DEFAULT_OPENAI
        else:
            if args.auto:
                base = args.base_url or picker(state, True)
            else:
                if getattr(args, "yes", False) and not args.base_url:
                    err("--yes provided but no --base-url; refusing to prompt.")
                    sys.exit(2)
                base = args.base_url or picker(state, False)
        state.base_url = base
    else:
        # Non full-auto: if --auto provided, still perform detection once; otherwise editor will handle it
        if args.auto:
            base = args.base_url or picker(state, True)
            state.base_url = base
        else:
            state.base_url = args.base_url or state.base_url or ""

    # Infer a safe default provider from the base URL (localhost:1234 → lmstudio, 11434 → ollama, otherwise 'custom').
    default_provider = resolve_provider(state.base_url or "")
    state.provider = args.provider or default_provider
    # If provider is OpenAI and no base provided, normalize to default OpenAI endpoint
    if state.provider == "openai" and not state.base_url:
        from .spec import DEFAULT_OPENAI

        state.base_url = DEFAULT_OPENAI
    if state.provider == "custom":
        # Avoid prompting in non-interactive runs
        if not (args.full_auto or args.auto or getattr(args, "yes", False)):
            state.provider = (
                input(
                    "Provider id to use in model_providers (e.g., myprovider): "
                ).strip()
                or "custom"
            )

    # If targeting OpenAI interactively, allow choosing auth method (API vs ChatGPT)
    if state.provider == "openai" and not args.auto and not getattr(args, "yes", False):
        print()
        print(c("OpenAI authentication method:", CYAN))
        idx = prompt_choice(
            "Select",
            [
                "API key (preferred_auth_method=apikey)",
                "ChatGPT (preferred_auth_method=chatgpt)",
            ],
        )
        args.preferred_auth_method = "apikey" if idx == 0 else "chatgpt"

    if args.provider:
        state.profile = args.profile or args.provider
    else:
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
        # Default env var names by provider
        default_envs = {
            "openai": "OPENAI_API_KEY",
            "openrouter-remote": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "cohere": "COHERE_API_KEY",
            "baseten": "BASETEN_API_KEY",
        }
        if not state.env_key or state.env_key == "NULLKEY":
            state.env_key = default_envs.get(state.provider, state.env_key or "NULLKEY")

    # In interactive OpenAI API-key mode, offer to set/update OPENAI_API_KEY in auth.json
    if (
        state.provider == "openai"
        and (args.preferred_auth_method or "apikey") == "apikey"
        and not getattr(args, "yes", False)
        and not getattr(args, "dry_run", False)
        and not getattr(args, "_ran_editor", False)
    ):
        import json
        import getpass

        existing_val = ""
        if AUTH_JSON.exists():
            try:
                data = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    existing_val = str(data.get("OPENAI_API_KEY") or "")
            except Exception:
                existing_val = ""
        if existing_val:
            do_update = prompt_yes_no(
                f"Found existing OPENAI_API_KEY in {AUTH_JSON.name}. Update it?",
                default=False,
            )
        else:
            do_update = prompt_yes_no(
                f"Set OPENAI_API_KEY now in {AUTH_JSON.name}?", default=True
            )
        if do_update:
            try:
                new_key = getpass.getpass(
                    "Enter OPENAI_API_KEY (input hidden): "
                ).strip()
            except Exception as exc:  # pragma: no cover
                err(f"Could not read input: {exc}")
                sys.exit(2)
            if new_key:
                # Write to ~/.codex/auth.json
                home.mkdir(parents=True, exist_ok=True)
                data = {}
                if AUTH_JSON.exists():
                    try:
                        data = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
                        if not isinstance(data, dict):
                            data = {}
                    except Exception:
                        data = {}
                data["OPENAI_API_KEY"] = new_key
                atomic_write_with_backup(AUTH_JSON, json.dumps(data, indent=2) + "\n")
                ok(f"Updated {AUTH_JSON} with OPENAI_API_KEY")
                warn("Never commit this file; it contains a secret.")

    # Offer unified interactive editor unless full-auto is requested
    interactive_action = None
    if not args.full_auto:
        # Invoke editor by default with no CLI args, or when explicitly managing profiles/MCP
        trigger_editor = bool(getattr(args, "_no_args", False))
        trigger_editor = trigger_editor or getattr(args, "manage_profiles", False) or getattr(args, "manage_mcp", False)
        if trigger_editor:
            interactive_action = interactive_settings_editor(state, args)
            if interactive_action == "quit":
                info("Aborted without writing.")
                return
            if interactive_action == "overwrite":
                args.overwrite_profile = True
            # Fast write mode: avoid legacy pipeline prompts; use current state/args
            if interactive_action in ("write", "write_and_launch"):
                setattr(args, "_fast_write", True)
    # Model selection: Only old pipeline for full-auto. If explicit --model provided, respect it.
    if args.model:
        target = args.model
        chosen = target
        try:
            lm = getattr(
                sys.modules.get("codex_cli_linker"), "list_models", list_models
            )
            models = [] if state.provider == "openai" else lm(state.base_url)
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
    elif (
        (args.full_auto or args.auto)
        and args.model_index is not None
        and state.provider != "openai"
    ):
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
    # Non full-auto legacy interactive: if no model was provided and no auto selection, prompt to pick
    if (not getattr(args, "_fast_write", False)) and (
        not args.full_auto
        and not args.auto
        and not args.model
        and state.provider != "openai"
    ):
        try:
            pmi = getattr(
                sys.modules.get("codex_cli_linker"),
                "pick_model_interactive",
                pick_model_interactive,
            )
            state.model = pmi(state.base_url, None)
            log_event("model_selected", provider=state.provider, model=state.model)
        except Exception as e:
            err(str(e))
            sys.exit(2)

    if not args.full_auto:
        # Keep legacy extra prompts minimal for now, since editor handled main knobs
        args._ran_editor = True
        pass
        if getattr(args, "manage_profiles", False):
            manage_profiles_interactive(args)
        if getattr(args, "manage_mcp", False):
            manage_mcp_servers_interactive(args)

    state.approval_policy = args.approval_policy
    state.sandbox_mode = args.sandbox_mode
    state.reasoning_effort = args.reasoning_effort
    state.reasoning_summary = args.reasoning_summary
    state.verbosity = args.verbosity
    state.disable_response_storage = args.disable_response_storage
    state.no_history = args.no_history
    state.history_max_bytes = args.history_max_bytes

    # Auto-detect context window if not provided
    if (args.model_context_window or 0) <= 0 and not getattr(args, "_fast_write", False):
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
            # Show pretty color diffs versus existing files (fallback to unified diff on no-color)
            def show_diff(path: Path, new_text: str, label: str):
                try:
                    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
                except Exception:
                    old_text = ""

                use_color = supports_color() and not os.environ.get("NO_COLOR")
                if use_color:
                    old = old_text.splitlines()
                    new = new_text.splitlines()
                    print()
                    print(c(f"≡ Diff: {path} → {label}", CYAN))
                    for line in difflib.ndiff(old, new):
                        if line.startswith("- "):
                            print(c("- " + line[2:], RED))
                        elif line.startswith("+ "):
                            print(c("+ " + line[2:], GREEN))
                        elif line.startswith("? "):
                            # Hints: alignment markers; de-emphasize
                            print(c("? " + line[2:], GRAY))
                        else:
                            # Unchanged
                            print(c("  " + line[2:], GRAY))
                else:
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

        # Optional safety: prevent overwriting an existing profile unless allowed
        import re as _re

        if config_toml.exists() and not getattr(args, "overwrite_profile", False):
            try:
                old_text = config_toml.read_text(encoding="utf-8")
            except Exception:
                old_text = ""
            prof = (args.profile or state.profile or state.provider).strip()
            if prof:
                pattern = _re.compile(
                    r"^\[profiles\.%s\]\s*$" % _re.escape(prof), _re.MULTILINE
                )
                if pattern.search(old_text):
                    if getattr(args, "yes", False):
                        err(
                            f"Profile '{prof}' exists. Pass --overwrite-profile or choose a new --profile."
                        )
                        sys.exit(2)
                    else:
                        if not prompt_yes_no(
                            f"Profile '{prof}' exists in config.toml. Overwrite it?",
                            default=False,
                        ):
                            err("Aborted to avoid overwriting existing profile.")
                            sys.exit(2)

        # Always write TOML; JSON/YAML only if flags requested. Normalize blank lines and ensure trailing newline.
        t0 = time.time()
        if getattr(args, "merge_profiles", False) and config_toml.exists():
            try:
                existing_text = config_toml.read_text(encoding="utf-8")
            except Exception:
                existing_text = ""
            # Extract only [profiles.*] blocks from new output
            import re as _re

            profile_blocks = []
            for m in _re.finditer(
                r"(?ms)^\[profiles\.([^\]]+)\]\s*.*?(?=^\[|\Z)", toml_out
            ):
                profile_blocks.append(m.group(0).rstrip())
            # Remove same-named blocks from existing
            merged_text = existing_text
            for blk in profile_blocks:
                header_m = _re.match(r"^\[profiles\.([^\]]+)\]", blk)
                if not header_m:
                    continue
                name = header_m.group(1)
                pat = _re.compile(
                    rf"(?ms)^\[profiles\.{_re.escape(name)}\]\s*.*?(?=^\[|\Z)"
                )
                merged_text = pat.sub("", merged_text)
            # Append new blocks at end
            frag = (
                ("\n\n" + "\n\n".join(profile_blocks) + "\n") if profile_blocks else ""
            )
            out_text = (
                (merged_text.rstrip() + frag + "\n").lstrip("\n") if frag else toml_out
            )
            atomic_write_with_backup(config_toml, _re.sub(r"\n{3,}", "\n\n", out_text))
        else:
            # Optional full-config merge with conflict checks
            if getattr(args, "merge_config", False) and config_toml.exists():
                try:
                    existing_text = config_toml.read_text(encoding="utf-8")
                except Exception:
                    existing_text = ""
                import re as _re

                new_text = toml_out
                merged = existing_text
                conflicts = []
                # Root keys
                root_lines = []
                for line in new_text.splitlines():
                    if line.strip().startswith("["):
                        break
                    if line.strip().startswith("#") or not line.strip():
                        continue
                    if "=" in line:
                        k = line.split("=", 1)[0].strip()
                        root_lines.append((k, line))
                for k, line in root_lines:
                    if _re.search(rf"(?m)^\s*{_re.escape(k)}\s*=", existing_text):
                        conflicts.append(k)
                    else:
                        merged = merged.rstrip() + "\n" + line + "\n"
                # Simple sections
                for sec in ("tools", "history", "sandbox_workspace_write", "tui"):
                    m = _re.search(
                        rf"(?ms)^\[{_re.escape(sec)}\]\s*.*?(?=^\[|\Z)", new_text
                    )
                    if not m:
                        continue
                    if _re.search(rf"(?m)^\[{_re.escape(sec)}\]\s*$", existing_text):
                        conflicts.append(f"[{sec}]")
                    else:
                        merged = merged.rstrip() + "\n\n" + m.group(0).rstrip() + "\n"

                # Namespaced tables
                def merge_ns(prefix: str):
                    nonlocal merged
                    for m2 in _re.finditer(
                        rf"(?ms)^\[{_re.escape(prefix)}\.([^\]]+)\]\s*.*?(?=^\[|\Z)",
                        new_text,
                    ):
                        name = m2.group(1)
                        hdr_pat = (
                            rf"(?m)^\[{_re.escape(prefix)}\.{_re.escape(name)}\]\s*$"
                        )
                        if _re.search(hdr_pat, existing_text):
                            conflicts.append(f"[{prefix}.{name}]")
                        else:
                            merged = (
                                merged.rstrip() + "\n\n" + m2.group(0).rstrip() + "\n"
                            )

                for pf in ("model_providers", "profiles", "mcp_servers"):
                    merge_ns(pf)
                if conflicts and not getattr(args, "merge_overwrite", False):
                    if getattr(args, "yes", False):
                        err(
                            "Merge conflicts detected; re-run with --merge-overwrite to replace them."
                        )
                        sys.exit(2)
                    info("Merge conflicts detected (will overwrite if confirmed):")
                    for citem in conflicts:
                        print(c(f"  {citem}", CYAN))
                    if not prompt_yes_no(
                        "Overwrite conflicting entries?", default=False
                    ):
                        err("Aborting merge to avoid overwriting.")
                        sys.exit(2)
                # Overwrite conflicts
                for citem in conflicts:
                    if citem.startswith("["):
                        sec = citem.strip("[]")
                        pat = _re.compile(
                            rf"(?ms)^\[{_re.escape(sec)}\]\s*.*?(?=^\[|\Z)"
                        )
                        merged = pat.sub("", merged)
                        m3 = _re.search(pat, new_text)
                        if m3:
                            merged = (
                                merged.rstrip() + "\n\n" + m3.group(0).rstrip() + "\n"
                            )
                    else:
                        pat = _re.compile(rf"(?m)^\s*{_re.escape(citem)}\s*=.*$")
                        merged = pat.sub("", merged)
                        for k, line in root_lines:
                            if k == citem:
                                merged = merged.rstrip() + "\n" + line + "\n"
                                break
                out_text = _re.sub(r"\n{3,}", "\n\n", merged).strip() + "\n"
                atomic_write_with_backup(config_toml, out_text)
            else:
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

    # Respect no auto-launch policy: only print how to launch when requested
    if interactive_action == "write_and_launch":
        info("Launch Codex manually with:")
        print(c(f"  npx codex --profile {state.profile}", CYAN))
        print(c(f"  codex --profile {state.profile}", CYAN))


__all__ = ["main"]
