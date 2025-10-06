"""Detection and model listing helpers.

Lightweight utilities to discover a local OpenAI‑compatible server and inspect
its advertised models without third‑party dependencies. These helpers are used
by interactive flows and the doctor diagnostics.

Design notes
- Short timeouts and best‑effort behavior; prefer returning ``None``/``[]`` or
  ``0`` over raising, except where a caller explicitly expects an error.
- ``detect_base_url`` probes well‑known localhost candidates concurrently and
  returns the first that responds to ``/models``.
"""

from __future__ import annotations
import concurrent.futures
from typing import List, Optional
import logging
import sys

from .spec import COMMON_BASE_URLS
from .utils import http_get_json, log_event
from .ui import info, ok, warn, c, GRAY


def detect_base_url(candidates: List[str] = COMMON_BASE_URLS) -> Optional[str]:
    """Return the first base URL that responds to ``/models``.

    Probes ``candidates`` concurrently with short timeouts, logging a brief
    line for each failed candidate. Returns the winning base URL, or ``None``
    when none respond.
    """
    logging.info("Auto-detecting OpenAI-compatible servers")
    info("Auto‑detecting OpenAI‑compatible servers…")

    def probe(base: str):
        logging.debug("Probing %s", base)
        url = base.rstrip("/") + "/models"
        http = getattr(
            sys.modules.get("codex_cli_linker"), "http_get_json", http_get_json
        )
        try:
            return base, http(url, timeout=1.5)
        except TypeError:  # tests may stub without timeout kw
            return base, http(url)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates))
    futures = [executor.submit(probe, base) for base in candidates]
    try:
        for fut in concurrent.futures.as_completed(futures):
            base, (data, err_) = fut.result()
            if data and isinstance(data, dict) and "data" in data:
                logging.info("Detected server at %s", base)
                ok(f"Detected server: {base}")
                try:
                    log_event("probe_success", path=base)
                except Exception:
                    pass
                executor.shutdown(wait=False, cancel_futures=True)
                return base
            else:
                logging.debug("No response from %s: %s", base, err_)
                print(c(f"  • {base} not responding to /models ({err_})", GRAY))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    logging.warning("No server auto-detected")
    warn("No server auto‑detected.")
    return None


def list_models(base_url: str) -> List[str]:
    """Fetch and return the list of model ids from ``/models``.

    Raises ``RuntimeError`` when the endpoint cannot be fetched.
    """
    http = getattr(sys.modules.get("codex_cli_linker"), "http_get_json", http_get_json)
    data, err_ = http(base_url.rstrip("/") + "/models")
    if not data:
        raise RuntimeError(f"Failed to fetch models from {base_url}/models: {err_}")
    return [it.get("id") for it in (data.get("data") or []) if it.get("id")]


def try_auto_context_window(base_url: str, model_id: str) -> int:
    """Return a best‑effort context window detected from ``/models`` metadata.

    Looks for common metadata keys (``context_length``, ``n_ctx``, etc.) on
    the entry matching ``model_id``; falls back to scanning other entries. On
    failure, returns ``0``.
    """
    http = getattr(sys.modules.get("codex_cli_linker"), "http_get_json", http_get_json)
    data, _ = http(base_url.rstrip("/") + "/models")
    if not data or "data" not in data or not isinstance(data["data"], list):
        return 0

    def extract_ctx(meta: dict) -> int:
        for k in (
            "context_length",
            "max_context_length",
            "context_window",
            "max_context_window",
            "n_ctx",
        ):
            val = meta.get(k)
            if isinstance(val, int) and val > 0:
                return val
            for subkey in ("metadata", "settings", "config", "parameters"):
                sub = meta.get(subkey)
                if isinstance(sub, dict):
                    sub_val = sub.get(k)
                    if isinstance(sub_val, int) and sub_val > 0:
                        return sub_val
        return 0

    for it in data["data"]:
        if it.get("id") == model_id:
            ctx = extract_ctx(it) or extract_ctx(
                it.get("meta", {}) if isinstance(it.get("meta"), dict) else {}
            )
            if ctx:
                return ctx

    for it in data["data"]:
        ctx = extract_ctx(it) or extract_ctx(
            it.get("meta", {}) if isinstance(it.get("meta"), dict) else {}
        )
        if ctx:
            return ctx
    return 0


__all__ = [
    "detect_base_url",
    "list_models",
    "try_auto_context_window",
]
