"""Authentication-related interactive flows.

Currently encapsulates the optional prompt to set or update OPENAI_API_KEY in
the auth.json store when the user is targeting the OpenAI provider with API key
mode and is not in non-interactive mode.
"""

from __future__ import annotations

import json
import getpass
from pathlib import Path

from .io_safe import AUTH_JSON, atomic_write_with_backup
from .ui import ok, warn, err
from .prompts import prompt_yes_no


def maybe_prompt_openai_key(args, home: Path) -> None:
    """Offer to set/update OPENAI_API_KEY in auth.json under CODEX_HOME.

    This function mirrors the previous inline behavior in the main flow and is
    a no-op for non-OpenAI providers or when non-interactive flags are set.
    """
    if not (
        getattr(args, "provider", "") == "openai"
        and (getattr(args, "preferred_auth_method", "") or "apikey") == "apikey"
        and not getattr(args, "yes", False)
        and not getattr(args, "dry_run", False)
        and not getattr(args, "_ran_editor", False)
    ):
        return

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
    if not do_update:
        return

    try:
        new_key = getpass.getpass("Enter OPENAI_API_KEY (input hidden): ").strip()
    except Exception as exc:  # pragma: no cover
        err(f"Could not read input: {exc}")
        raise SystemExit(2)
    if not new_key:
        return
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


__all__ = ["maybe_prompt_openai_key"]
