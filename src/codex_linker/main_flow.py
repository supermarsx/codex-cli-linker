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
    interactive_settings_editor,
    manage_profiles_interactive,
    manage_mcp_servers_interactive,
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
from .updates_helpers import _log_update_sources, _report_update_status
from .doctor import run_doctor
from .migrate import migrate_configs_to_linker
from .auth_flow import maybe_prompt_openai_key
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
)


# _log_update_sources and _report_update_status are imported from updates_helpers


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
    # Early exits / forced update check / version
    if handle_early_exits(
        args,
        home,
        config_targets=[config_toml, config_json, config_yaml],
        current_version=current_version,
        install_origin=install_origin,
        update_sources=update_sources,
    ):
        return
    # Consolidate legacy config files into linker_config.json early
    # Skip during --dry-run to honor tests and avoid writes
    if not getattr(args, "dry_run", False):
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
    # Startup: banner is part of the main hub; optionally clear and print a minimal title here
    is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    color_ok = not os.environ.get("NO_COLOR")
    should_clear = is_tty and color_ok and (os.name != "nt" or getattr(args, "clear", False))
    if should_clear:
        clear_screen()
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
    interactive_action = None
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
            # Guided pipeline replaces legacy: run dedicated flow
            if interactive_action == "legacy":
                try:
                    from .guided_pipeline import run_guided_pipeline

                    run_guided_pipeline(state, args)
                    if getattr(args, "_guided_abort", False):
                        info("Aborted without writing.")
                        return
                except Exception as e:
                    err(str(e))
                    sys.exit(2)
    # Model selection
    choose_model(args, state)

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

    if False and args.dry_run:
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
    elif False:
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

    # Friendly summary and hints
    print_summary_and_hints(args, state, config_toml=config_toml)


__all__ = ["main"]
