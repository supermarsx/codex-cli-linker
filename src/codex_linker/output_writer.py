"""Output writing and diff/merge helpers.

Encapsulates the logic for rendering config outputs (TOML/JSON/YAML), printing
diffs in dry-run mode, merging into existing TOML when requested, and writing
files with backups.

Functions in this module are side-effecting by design (I/O, printing). Keep
the call surface narrow from main flow and document behaviors in docstrings.
"""

from __future__ import annotations

import difflib
import os
import re as _re
import time
from pathlib import Path
from typing import Dict

from .emit import to_json, to_yaml
from .io_safe import atomic_write_with_backup
from .prompts import prompt_yes_no
from .ui import c, CYAN, RED, GREEN, GRAY, ok, err, info, supports_color
from .logging_utils import log_event


def _show_diff(path: Path, new_text: str, label: str) -> None:
    """Print a unified or colorized diff between existing file and ``new_text``.

    Uses color when supported; otherwise prints a unified diff. Non-fatal on
    read errors and treats missing files as empty.
    """
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
                print(c("? " + line[2:], GRAY))
            else:
                print(c("  " + line[2:], GRAY))
    else:
        diff = difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{label} (proposed)",
        )
        import sys as _sys

        _sys.stdout.writelines(diff)


def _merge_append_sections(existing: str, new_text: str, conflicts: list[str]) -> str:
    """Merge root keys and well-known sections, recording conflicts.

    Appends sections that do not already exist; populates ``conflicts`` when a
    section/root key already exists, to be handled at a higher level.
    """
    merged = existing
    # Root keys: copy missing ones
    root_lines = []
    for line in new_text.splitlines():
        if line.strip().startswith("["):
            break
        if "=" in line:
            root_lines.append((line.split("=", 1)[0].strip(), line))
    for k, line in root_lines:
        pat = _re.compile(rf"(?m)^\s*{_re.escape(k)}\s*=.*$")
        if not _re.search(pat, merged):
            merged = merged.rstrip() + "\n" + line + "\n"

    def merge_ns(ns: str) -> None:
        nonlocal merged
        pat = _re.compile(rf"(?ms)^\[{_re.escape(ns)}\]\s*.*?(?=^\[|\Z)")
        m1 = _re.search(pat, merged)
        m2 = _re.search(pat, new_text)
        if m1 and m2:
            conflicts.append(f"[{ns}]")
        elif m2:
            # Append the whole section from new_text
            block = m2.group(0).rstrip()
            if block:
                merged = merged.rstrip() + "\n\n" + block + "\n"

    for pf in ("model_providers", "profiles", "mcp_servers"):
        merge_ns(pf)
    return merged


def handle_outputs(
    args,
    cfg: Dict,
    toml_out: str,
    *,
    config_toml: Path,
    config_json: Path,
    config_yaml: Path,
    home: Path,
    state_profile: str,
) -> None:
    """Render and write outputs according to CLI flags, including diffs/merge.

    Mirrors the prior inline implementation, with identical prompts and messages.
    """
    if args.dry_run:
        if getattr(args, "diff", False):
            _show_diff(config_toml, toml_out, "config.toml")
            if args.json:
                _show_diff(config_json, to_json(cfg), "config.json")
            if args.yaml:
                _show_diff(config_yaml, to_yaml(cfg), "config.yaml")
        else:
            print(toml_out, end="")
            if args.json:
                print(to_json(cfg))
            if args.yaml:
                print(to_yaml(cfg))
        info("Dry run: no files were written.")
        return

    # Ensure destination dir exists
    home.mkdir(parents=True, exist_ok=True)

    # Optional safety: prevent overwriting an existing profile unless allowed
    import re as _re

    if config_toml.exists() and not getattr(args, "overwrite_profile", False):
        try:
            old_text = config_toml.read_text(encoding="utf-8")
        except Exception:
            old_text = ""
        prof = (getattr(args, "profile", "") or state_profile).strip()
        if prof:
            pattern = _re.compile(
                r"^\[profiles\.%s\]\s*$" % _re.escape(prof), _re.MULTILINE
            )
            if pattern.search(old_text):
                if getattr(args, "yes", False):
                    err(
                        f"Profile '{prof}' exists. Pass --overwrite-profile or choose a new --profile."
                    )
                    raise SystemExit(2)
                else:
                    if not prompt_yes_no(
                        f"Profile '{prof}' exists in config.toml. Overwrite it?",
                        default=False,
                    ):
                        err("Aborted to avoid overwriting existing profile.")
                        raise SystemExit(2)

    t0 = time.time()
    if args.merge_config or args.merge_profiles:
        try:
            old = (
                config_toml.read_text(encoding="utf-8") if config_toml.exists() else ""
            )
        except Exception:
            old = ""
        new_text = toml_out
        conflicts: list[str] = []
        merged = _merge_append_sections(old, new_text, conflicts)
        if conflicts and not getattr(args, "merge_overwrite", False):
            if getattr(args, "yes", False):
                err(
                    "Merge conflicts detected; re-run with --merge-overwrite to replace them."
                )
                raise SystemExit(2)
            info("Merge conflicts detected (will overwrite if confirmed):")
            for citem in conflicts:
                print(c(f"  {citem}", CYAN))
            if not prompt_yes_no("Overwrite conflicting entries?", default=False):
                err("Aborting merge to avoid overwriting.")
                raise SystemExit(2)
        # Overwrite conflicting sections/keys from new_text
        if conflicts:
            for citem in conflicts:
                if citem.startswith("["):
                    sec = citem.strip("[]")
                    pat = _re.compile(rf"(?ms)^\[{_re.escape(sec)}\]\s*.*?(?=^\[|\Z)")
                    merged = pat.sub("", merged)
                    m3 = _re.search(pat, new_text)
                    if m3:
                        merged = merged.rstrip() + "\n\n" + m3.group(0).rstrip() + "\n"
                else:
                    pat = _re.compile(rf"(?m)^\s*{_re.escape(citem)}\s*=.*$")
                    merged = pat.sub("", merged)
        out_text = _re.sub(r"\n{3,}", "\n\n", merged).strip() + "\n"
        atomic_write_with_backup(config_toml, out_text)
    else:
        atomic_write_with_backup(config_toml, toml_out)

    log_event(
        "write_config",
        provider=getattr(args, "provider", ""),
        model=getattr(args, "model", ""),
        path=str(config_toml),
        duration_ms=int((time.time() - t0) * 1000),
    )
    ok(f"Wrote {config_toml}")

    if args.json:
        t1 = time.time()
        atomic_write_with_backup(config_json, to_json(cfg))
        log_event(
            "write_config",
            provider=getattr(args, "provider", ""),
            model=getattr(args, "model", ""),
            path=str(config_json),
            duration_ms=int((time.time() - t1) * 1000),
        )
        ok(f"Wrote {config_json}")

    if args.yaml:
        t2 = time.time()
        atomic_write_with_backup(config_yaml, to_yaml(cfg))
        log_event(
            "write_config",
            provider=getattr(args, "provider", ""),
            model=getattr(args, "model", ""),
            path=str(config_yaml),
            duration_ms=int((time.time() - t2) * 1000),
        )
        ok(f"Wrote {config_yaml}")


__all__ = ["handle_outputs"]
