"""Detection and model listing helpers."""

from __future__ import annotations
import concurrent.futures
from typing import List, Optional
import logging
import sys

from .spec import COMMON_BASE_URLS
from .utils import http_get_json, log_event
from .ui import info, ok, warn, c, GRAY


def detect_base_url(candidates: List[str] = COMMON_BASE_URLS) -> Optional[str]:
    """Probe a few common local servers for an OpenAI-compatible /models endpoint."""
    logging.info("Auto-detecting OpenAI-compatible servers")
    info("Auto‑detecting OpenAI‑compatible servers…")

    def probe(base: str):
        logging.debug("Probing %s", base)
        url = base.rstrip("/") + "/models"
        http = getattr(sys.modules.get("codex_cli_linker"), "http_get_json", http_get_json)
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
    """Return the list of model IDs advertised by the server."""
    http = getattr(sys.modules.get("codex_cli_linker"), "http_get_json", http_get_json)
    data, err_ = http(base_url.rstrip("/") + "/models")
    if not data:
        raise RuntimeError(f"Failed to fetch models from {base_url}/models: {err_}")
    return [it.get("id") for it in (data.get("data") or []) if it.get("id")]


def try_auto_context_window(base_url: str, model_id: str) -> int:
    """Best-effort context window detection via /models metadata."""
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
