from __future__ import annotations

import sys
from ..detect import list_models
from ..prompts import pick_model_interactive
from ..ui import ok, err
from ..logging_utils import log_event


def choose_model(args, state) -> None:
    """Resolve model selection via explicit, auto, or interactive paths."""
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
        return
    # Auto path
    if (
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
            raise SystemExit(2)
        return
    # Interactive legacy picker
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
            raise SystemExit(2)
