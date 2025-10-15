"""Interactive guided setup pipeline.

Provides a single, linear flow that walks the user through selecting a
provider, base URL, auth env key (and optionally capturing a secret), wire
protocol, query params, headers, model, context window, and general policies.

The goal is to offer a one‑stop, friendly path that sets ``args`` and
``state`` consistently so downstream rendering and writing can proceed without
additional prompts. The flow honors ``--no-emojis`` and keeps all decisions
reversible via the hub or subsequent edits.
"""

from __future__ import annotations

from typing import Dict

from .state import LinkerState
from .ui import c, BOLD, CYAN, ok, warn, err
from .spec import PROVIDER_LABELS
from .detect import list_models, try_auto_context_window
from .io_safe import AUTH_JSON, write_auth_json_merge
from .prompts.input_utils import (
    prompt_choice,
    _safe_input,
    _parse_brace_kv,
    fmt,
    set_emojis_enabled,
)
from .prompts.providers import _default_base_for_provider_id


def run_guided_pipeline(state: LinkerState, args) -> None:
    """Run the step-by-step guided setup and populate ``args``/``state``.

    Parameters
    - ``state``: Current :class:`LinkerState` (updated with provider/base/env).
    - ``args``: Parsed CLI args (updated in-place with guided selections).

    Sequence (high level)
    1) Choose provider (presets/manually/existing) and set ``args.provider``.
    2) Configure base URL (auto/default/manual) and update ``state.base_url``.
    3) Choose env key name and optionally capture a secret into ``auth.json``.
    4) Select wire API (chat/responses/auto based on provider).
    5) Provide query params (manual or Azure api-version convenience).
    6) Add HTTP headers (static CSV and/or env-sourced CSV) as overrides.
    7) Choose model (manual/auto-detect/default fallback).
    8) Set context window (auto/manual/skip), and max output tokens.
    9) Set approval policy + sandbox mode.
    10) Fine-tune reasoning effort/summary/verbosity and retry/timeout knobs.
    11) Enable optional tools (web search) and set notify targets.
    12) Show summary and ask to write (or write+launch) or abort.

    Side effects
    - May write the secret to ``AUTH_JSON`` via ``write_auth_json_merge``.
    - Stashes provider-specific overrides in ``args.provider_overrides``.
    - Sets private flags consumed by the main flow (``_guided_abort``,
      ``_guided_action``, ``_fast_write``).
    """
    set_emojis_enabled(not getattr(args, "no_emojis", False))
    print()
    print(c(fmt("Guided setup 🧭"), BOLD))

    # 1) Provider selection
    print()
    print(c(fmt("Select a provider 🔌"), BOLD))
    mode = prompt_choice(
        "Choose",
        [
            "Pick from presets",
            "Enter id manually",
            "Use existing active",
        ],
    )
    if mode == 0:
        preset_ids = sorted(
            PROVIDER_LABELS.keys(), key=lambda k: PROVIDER_LABELS[k].lower()
        )
        labels = [f"{PROVIDER_LABELS[k]} ({k})" for k in preset_ids]
        pi = prompt_choice("Preset", labels)
        pid = preset_ids[pi]
    elif mode == 1:
        pid = _safe_input("Provider id (e.g., openai, ollama, azure): ").strip()
        if not pid:
            pid = args.provider or state.provider or "openai"
    else:
        pid = args.provider or state.provider or "openai"
    args.provider = pid
    state.provider = pid

    # 2) Base URL: offer auto-detect or manual/default
    print()
    print(c(fmt("Configure base URL 🌐"), BOLD))
    base_choice = prompt_choice(
        "Base URL",
        [
            "Auto-detect",
            "Use default for preset",
            "Enter manually",
        ],
    )
    if base_choice == 0:
        try:
            from .prompts.base_pick import pick_base_url  # reuse existing logic

            state.base_url = pick_base_url(state, auto=True)
        except Exception as e:
            warn(f"Auto-detect failed: {e}")
            state.base_url = _default_base_for_provider_id(pid)
    elif base_choice == 1:
        state.base_url = _default_base_for_provider_id(pid)
    else:
        state.base_url = _safe_input("Base URL (e.g., https://host:port/v1): ").strip()

    # 3) Env key and optional secret capture
    print()
    print(c(fmt("API key env var 🔐"), BOLD))
    default_env = {
        "openai": "OPENAI_API_KEY",
        "openrouter-remote": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "cohere": "COHERE_API_KEY",
        "baseten": "BASETEN_API_KEY",
    }.get(pid, f"{pid.upper().replace('-', '_')}_API_KEY")
    envk = _safe_input(f"Env key name [{default_env}]: ").strip() or default_env
    state.env_key = envk
    try:
        import getpass

        secret = getpass.getpass(
            f"Enter API key for {pid} (env {envk}) [blank to skip]: "
        ).strip()
    except Exception:
        secret = _safe_input(
            f"Enter API key for {pid} (env {envk}) [blank to skip]: "
        ).strip()
    if secret:
        try:
            write_auth_json_merge(AUTH_JSON, {envk: secret})
            ok(f"Updated {AUTH_JSON} with {envk}")
            warn("Never commit this file; it contains a secret.")
        except Exception as e:
            err(f"Could not update {AUTH_JSON}: {e}")

    # 4) Wire API
    print()
    print(c(fmt("Wire protocol"), BOLD))
    wi = prompt_choice("Wire API", ["chat", "responses", "Auto (use sensible default)"])
    if wi < 2:
        args.wire_api = ["chat", "responses"][wi]
    else:
        args.wire_api = "responses" if pid == "azure" else "chat"

    # 5) Query params (e.g., Azure api-version)
    print()
    print(c(fmt("Query params"), BOLD))
    qp_mode = prompt_choice(
        "Provide query params",
        ["Skip", 'Enter ({key="value",...})', "Azure api-version only"],
    )
    qpi: Dict[str, str] = {}
    if qp_mode == 1:
        raw = _safe_input("Query params object: ").strip()
        if raw:
            qpi = _parse_brace_kv(raw)
    elif qp_mode == 2:
        apiver = _safe_input("Azure api-version (e.g., 2025-04-01-preview): ").strip()
        if apiver:
            qpi = {"api-version": apiver}
        args.azure_api_version = apiver
    if qpi:
        # stash under provider_overrides for rendering
        po = getattr(args, "provider_overrides", {}) or {}
        entry = dict(po.get(pid) or {})
        entry["query_params"] = qpi
        po[pid] = entry
        args.provider_overrides = po

    # 6) HTTP headers
    print()
    print(c(fmt("HTTP headers"), BOLD))
    hm = prompt_choice(
        "Headers", ["None", "CSV headers (KEY=VAL)", "Env headers (KEY=ENV)"]
    )
    if hm == 1:
        raw = _safe_input("Headers CSV: ").strip()
        if raw:
            hmap: Dict[str, str] = {}
            for pair in raw.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    if k.strip():
                        hmap[k.strip()] = v.strip()
            if hmap:
                po = getattr(args, "provider_overrides", {}) or {}
                entry = dict(po.get(pid) or {})
                entry["http_headers"] = hmap
                po[pid] = entry
                args.provider_overrides = po
    elif hm == 2:
        raw = _safe_input("Env headers CSV (KEY=ENV): ").strip()
        if raw:
            hmap2: Dict[str, str] = {}
            for pair in raw.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    if k.strip():
                        hmap2[k.strip()] = v.strip()
            if hmap2:
                po = getattr(args, "provider_overrides", {}) or {}
                entry = dict(po.get(pid) or {})
                entry["env_http_headers"] = hmap2
                po[pid] = entry
                args.provider_overrides = po

    # 7) Model selection
    print()
    print(c(fmt("Model selection"), BOLD))
    mm = prompt_choice(
        "Model", ["Enter manually", "Auto-detect from server", "Use default (gpt-5)"]
    )
    if mm == 0:
        args.model = _safe_input("Model id: ").strip()
    elif mm == 1:
        try:
            models = list_models(state.base_url)
            if models:
                pick = prompt_choice("Choose model", models)
                args.model = models[pick]
            else:
                warn("No models returned; leaving default.")
        except Exception as e:
            err(f"Model detection failed: {e}")
    else:
        args.model = args.model or "gpt-5"

    # 8) Context window
    print()
    print(c(fmt("Context window"), BOLD))
    cw = prompt_choice("Context window", ["Auto-detect", "Enter value", "Skip"])
    if cw == 0:
        try:
            val = try_auto_context_window(state.base_url, args.model or "")
            if val > 0:
                args.model_context_window = val
                ok(f"Detected context window: {val} tokens")
        except Exception as e:
            warn(f"Detection failed: {e}")
    elif cw == 1:
        try:
            args.model_context_window = int(
                _safe_input("Context window: ").strip() or "0"
            )
        except Exception:
            pass

    # 9) Output tokens
    try:
        s = _safe_input("Max output tokens (blank to skip): ").strip()
        if s:
            args.model_max_output_tokens = int(s)
    except Exception:
        pass

    # 10) Approval/sandbox
    print()
    print(c(fmt("Approval & sandbox"), BOLD))
    ap = prompt_choice(
        "Approval policy", ["untrusted", "on-failure", "on-request", "never"]
    )
    args.approval_policy = ["untrusted", "on-failure", "on-request", "never"][ap]
    sb = prompt_choice(
        "Sandbox mode", ["read-only", "workspace-write", "danger-full-access"]
    )
    args.sandbox_mode = ["read-only", "workspace-write", "danger-full-access"][sb]

    # 11) Reasoning and verbosity
    re = prompt_choice(
        "Reasoning effort", ["minimal", "low", "medium", "high", "auto", "Skip"]
    )
    if re < 5:
        args.reasoning_effort = ["minimal", "low", "medium", "high", "auto"][re]
    rs = prompt_choice(
        "Reasoning summary", ["auto", "concise", "detailed", "none", "Skip"]
    )
    if rs < 4:
        args.reasoning_summary = ["auto", "concise", "detailed", "none"][rs]
    vb = prompt_choice("Verbosity", ["low", "medium", "high", "Skip"])
    if vb < 3:
        args.verbosity = ["low", "medium", "high"][vb]

    # 12) Retries/timeouts
    try:
        s = _safe_input("Request max retries (blank=skip): ").strip()
        if s:
            args.request_max_retries = int(s)
    except Exception:
        pass
    try:
        s = _safe_input("Stream max retries (blank=skip): ").strip()
        if s:
            args.stream_max_retries = int(s)
    except Exception:
        pass
    try:
        s = _safe_input("Stream idle timeout ms (blank=skip): ").strip()
        if s:
            args.stream_idle_timeout_ms = int(s)
    except Exception:
        pass

    # 13) Tools: web_search
    tw = prompt_choice("Enable web search tool?", ["No", "Yes"])  # default off
    args.tools_web_search = True if tw == 1 else False

    # 14) Notify
    s = _safe_input(
        'Notify JSON array (e.g., ["-y", "mcp-server"]) [blank=skip]: '
    ).strip()
    if s:
        args.notify = s

    # Summary and confirmation
    print()
    print(c(fmt("Summary"), BOLD))
    print(c(f"  provider: {args.provider}", CYAN))
    print(c(f"  base_url: {state.base_url}", CYAN))
    print(c(f"  env_key: {state.env_key or ''}", CYAN))
    print(c(f"  wire_api: {getattr(args, 'wire_api', '')}", CYAN))
    print(c(f"  model: {args.model or ''}", CYAN))
    print(c(f"  context_window: {getattr(args, 'model_context_window', 0) or 0}", CYAN))
    print(
        c(
            f"  max_output_tokens: {getattr(args, 'model_max_output_tokens', 0) or 0}",
            CYAN,
        )
    )
    print(c(f"  approval_policy: {args.approval_policy}", CYAN))
    print(c(f"  sandbox_mode: {args.sandbox_mode}", CYAN))
    print(c(f"  reasoning_effort: {getattr(args, 'reasoning_effort', '')}", CYAN))
    print(c(f"  reasoning_summary: {getattr(args, 'reasoning_summary', '')}", CYAN))
    print(c(f"  verbosity: {getattr(args, 'verbosity', '')}", CYAN))
    print(c(f"  request_max_retries: {getattr(args, 'request_max_retries', 0)}", CYAN))
    print(c(f"  stream_max_retries: {getattr(args, 'stream_max_retries', 0)}", CYAN))
    print(
        c(
            f"  stream_idle_timeout_ms: {getattr(args, 'stream_idle_timeout_ms', 0)}",
            CYAN,
        )
    )
    print()
    act = prompt_choice(
        "Next",
        [
            "Write now",
            "Write and launch (print cmd)",
            "Abort (back to hub)",
        ],
    )
    if act == 2:
        # Signal to main_flow to exit cleanly
        setattr(args, "_guided_abort", True)
        ok("Aborted; returning to hub.")
        return
    if act == 1:
        setattr(args, "_guided_action", "write_and_launch")
    # Guided pipeline confirmed – avoid legacy prompts later
    setattr(args, "_fast_write", True)
    ok("Guided setup complete. Writing configuration…")
