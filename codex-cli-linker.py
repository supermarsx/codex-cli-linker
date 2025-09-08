#!/usr/bin/env python3
"""
Codex CLI Linker

What this script does (quickly):
  • Detect a local OpenAI‑compatible server (LM Studio on :1234 or Ollama on :11434) or use a custom URL
  • Fetch available models from /v1/models and let you pick one
  • Generate a **Codex config** using the modern **config.toml** structure
      - Uses [model_providers.<id>] and [profiles.<name>] per the “# Config” reference
      - Includes per‑provider network tuning knobs (request/stream retries, idle timeout)
      - Adds a profile that pins your chosen provider/model and sane defaults
  • Can also emit **config.json** or **config.yaml** variants for people who want them alongside TOML
  • Backs up any existing config file before writing (adds .bak)
  • Saves a tiny linker JSON to remember your last choices

No external deps. Cross‑platform.

Usage examples:
  # NOTE: This tool ALWAYS writes TOML. It writes JSON/YAML only when --json or --yaml flags are provided.
  # Interactivity: When --auto is omitted, you will be asked to choose approval mode, reasoning effort,
  # sandbox mode. Auto-launch is disabled by design (never prompts, never launches).
  python codex-cli-linker.py                  # interactive (TOML, auto banner+clear)
  python codex-cli-linker.py --auto           # auto‑detect base URL
  python codex-cli-linker.py --base-url http://localhost:1234/v1 \
      --model llama-3.1-8b --provider lmstudio --profile lmstudio

  # Write JSON or YAML in addition to TOML:
  python codex-cli-linker.py --json
  python codex-cli-linker.py --yaml

"""

from __future__ import annotations
import argparse

try:
    # Python 3.8+: stdlib importlib.metadata
    from importlib.metadata import PackageNotFoundError, version as pkg_version
except Exception:  # pragma: no cover
    PackageNotFoundError = Exception  # type: ignore

    def pkg_version(_: str) -> str:  # type: ignore
        raise PackageNotFoundError


import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import re
import shlex
import urllib.error
import urllib.request
import urllib.parse
import concurrent.futures
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import difflib
import tempfile
import time

# Ensure default env for provider key if not set by the OS
os.environ.setdefault("NULLKEY", "nullkey")


# =============== UI helpers ===============
RESET = "[0m"
BOLD = "[1m"
DIM = "[2m"
RED = "[31m"
GREEN = "[32m"
YELLOW = "[33m"
BLUE = "[34m"
CYAN = "[36m"
GRAY = "[90m"


def supports_color() -> bool:
    """Return True if the terminal likely supports ANSI colors.

    Honor the actual TTY status; do not force color on Windows when stdout
    is not a TTY. This keeps tests predictable and avoids stray ANSI codes
    in redirected output.
    """
    try:
        if os.environ.get("NO_COLOR"):
            return False
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return False


def c(s: str, color: str) -> str:
    """Apply a color code when the terminal supports it."""
    return f"{color}{s}{RESET}" if supports_color() else s


def clear_screen():
    """Best effort attempt to clear the terminal, ignoring failures."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def banner():
    """Display the startup ASCII art banner."""
    art = r"""
                           _      _
          /               //     //         /
 _. __ __/ _  _., --- _. // o   // o ____  /_  _  __
(__(_)(_/_</_/ /\_   (__</_<_  </_<_/ / <_/ <_</_/ (_
                                                     
                                                    
"""
    print(c(art, CYAN))


def info(msg: str):
    """Print an informational message prefixed with ℹ."""
    print(c("ℹ ", BLUE) + msg)


def ok(msg: str):
    """Print a success message prefixed with a check mark."""
    print(c("✓ ", GREEN) + msg)


def warn(msg: str):
    """Print a warning message prefixed with an exclamation mark."""
    print(c("! ", YELLOW) + msg)


def err(msg: str):
    """Print an error message prefixed with a cross."""
    print(c("✗ ", RED) + msg)


# =============== Defaults/paths ===============
DEFAULT_LMSTUDIO = "http://localhost:1234/v1"
DEFAULT_OLLAMA = "http://localhost:11434/v1"
# Additional OpenAI-compatible local servers/shims
DEFAULT_VLLM = "http://localhost:8000/v1"
DEFAULT_TGWUI = "http://localhost:5000/v1"  # Text-Gen-WebUI OpenAI plugin
DEFAULT_TGI_8080 = "http://localhost:8080/v1"  # HF TGI shim
DEFAULT_TGI_3000 = "http://localhost:3000/v1"
DEFAULT_OPENROUTER_LOCAL = "http://localhost:7000/v1"
COMMON_BASE_URLS = [
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
]

# Friendly labels for known provider ids
PROVIDER_LABELS: Dict[str, str] = {
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
    "vllm": "vLLM",
    "tgwui": "Text-Gen-WebUI",
    "tgi": "TGI",
    "openrouter": "OpenRouter Local",
    "jan": "Jan",
    "llamafile": "Llamafile",
    "gpt4all": "GPT4All",
    "local": "Local LLM",
}

CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
CONFIG_TOML = CODEX_HOME / "config.toml"
CONFIG_JSON = CODEX_HOME / "config.json"
CONFIG_YAML = CODEX_HOME / "config.yaml"
LINKER_JSON = CODEX_HOME / "linker_config.json"


def get_version() -> str:
    """Return the tool version.

    Tries distribution metadata (when installed) and falls back to parsing
    pyproject.toml when running from source. Returns a sensible string even if
    neither source is available.
    """
    # 1) Installed via pip/wheel: use distribution metadata
    try:
        return pkg_version("codex-cli-linker")
    except Exception:
        pass

    # 2) Running from source: parse pyproject.toml next to this file
    try:
        root = Path(__file__).resolve().parent
        py = root / "pyproject.toml"
        if py.exists():
            txt = py.read_text(encoding="utf-8")
            import re as _re

            m = _re.search(r"(?ms)^\[project\].*?^version\s*=\s*\"([^\"]+)\"", txt)
            if m:
                return m.group(1)
    except Exception:
        pass

    return "0.0.0+unknown"


# =============== Data ===============
@dataclass
class LinkerState:
    """Persisted settings between runs to provide sensible defaults."""

    base_url: str = DEFAULT_LMSTUDIO
    provider: str = "lmstudio"  # provider id in [model_providers.<id>]
    profile: str = "lmstudio"  # profile name in [profiles.<name>]
    api_key: str = "sk-local"  # dummy value; local servers typically ignore
    env_key: str = "NULLKEY"  # DUMMY KEY; never store real secrets here
    model: str = ""  # chosen from /v1/models
    approval_policy: str = "on-failure"
    sandbox_mode: str = "workspace-write"
    reasoning_effort: str = "low"
    reasoning_summary: str = "auto"
    verbosity: str = "medium"
    disable_response_storage: bool = False
    no_history: bool = False
    history_max_bytes: int = 0

    def save(self, path: Path = LINKER_JSON):
        """Persist state to ``path`` in JSON format."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        ok(f"Saved linker config: {path}")

    @staticmethod
    def load(path: Path = LINKER_JSON) -> "LinkerState":
        """Load previously saved state, ignoring unexpected fields."""
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                allowed = {
                    k: v for k, v in data.items() if k in LinkerState.__annotations__
                }
                return LinkerState(**allowed)
        except Exception as e:
            warn(f"Could not load {path}: {e}")
        return LinkerState()


# =============== HTTP helpers ===============


def http_get_json(
    url: str, timeout: float = 3.0
) -> Tuple[Optional[dict], Optional[str]]:
    """Fetch JSON with a short timeout; return (data, error_message)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, str(e)


def detect_base_url(candidates: List[str] = COMMON_BASE_URLS) -> Optional[str]:
    """Probe a few common local servers for an OpenAI‑compatible /models endpoint."""
    logging.info("Auto-detecting OpenAI-compatible servers")
    info("Auto‑detecting OpenAI‑compatible servers…")

    def probe(base: str):
        logging.debug("Probing %s", base)
        url = base.rstrip("/") + "/models"
        try:
            return base, http_get_json(url, timeout=1.5)
        except TypeError:  # tests may stub without timeout kw
            return base, http_get_json(url)

    # Probe all candidates in parallel to reduce overall detection time. As soon
    # as one server responds, the remaining futures are cancelled to avoid
    # unnecessary network chatter.
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
    data, err_ = http_get_json(base_url.rstrip("/") + "/models")
    if not data:
        raise RuntimeError(f"Failed to fetch models from {base_url}/models: {err_}")
    return [it.get("id") for it in (data.get("data") or []) if it.get("id")]


# =============== Config emitters
# =============== Model metadata helpers ===============


def try_auto_context_window(base_url: str, model_id: str) -> int:
    """
    Best‑effort context window detection.
    Tries /v1/models and looks for common metadata fields used by local servers:
      • context_length, max_context_length, context_window, max_context_window, n_ctx
    Returns 0 if unknown.
    """
    data, err_ = http_get_json(base_url.rstrip("/") + "/models")
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
            v = meta.get(k)
            if isinstance(v, int) and v > 0:
                return v
            # sometimes nested under 'metadata' or 'settings'
            for subkey in ("metadata", "settings", "config", "parameters"):
                sub = meta.get(subkey)
                if (
                    isinstance(sub, dict)
                    and isinstance(sub.get(k), int)
                    and sub.get(k) > 0
                ):
                    return sub.get(k)
        return 0

    # scan for the chosen model, then try any model entry otherwise
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


# =============== Emitters (TOML/JSON/YAML) ===============


def backup(path: Path) -> Optional[Path]:
    """Backup existing file with a timestamped suffix. Returns backup path if created."""
    if path.exists():
        # Use a timestamped rename so previous configs remain recoverable. This
        # is fast (rename vs copy) and avoids accidental data loss if a new
        # configuration turns out to be broken.
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        bak = path.with_suffix(f"{path.suffix}.{stamp}.bak")
        try:
            path.replace(bak)
            info(f"Backed up existing {path.name} → {bak.name}")
        except Exception as e:
            warn(f"Backup failed: {e}")


def do_backup(path: Path) -> Optional[Path]:
    """Perform and announce a backup; returns the backup path if created."""
    try:
        if path.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M")
            bak = path.with_suffix(f"{path.suffix}.{stamp}.bak")
            path.replace(bak)
            info(f"Backed up existing {path.name} -> {bak.name}")
            return bak
    except Exception as e:  # pragma: no cover
        warn(f"Backup failed: {e}")
    return None


def atomic_write_with_backup(path: Path, text: str) -> Optional[Path]:
    """Atomically write UTF-8 text to `path` with fsync and optional .bak.

    - Writes to a temp file in the same directory
    - flushes and fsyncs the temp file
    - moves any existing target to a timestamped .bak
    - atomically replaces the target via os.replace
    Returns the backup path if created.
    """
    # Create temp file in same directory for atomic replace
    fd, tmppath = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        bak = do_backup(path)
        os.replace(tmppath, path)
        return bak
    except Exception:
        try:
            os.remove(tmppath)
        except Exception:
            pass
        raise


def build_config_dict(state: LinkerState, args: argparse.Namespace) -> Dict:
    """Translate runtime selections into a single dict that mirrors the TOML spec.
    This is the single source of truth for all emitters (TOML/JSON/YAML).
    """
    # Map to unified Python dict that mirrors the TOML structure in the spec
    cfg: Dict[str, object] = {
        # --- Root keys ---
        "model": args.model or state.model or "gpt-5",
        "model_provider": state.provider,
        "approval_policy": args.approval_policy,
        "sandbox_mode": args.sandbox_mode,
        "file_opener": args.file_opener,
        # --- Sandbox workspace‑write subtable (all defaults off/false) ---
        "sandbox_workspace_write": {
            "writable_roots": [],
            "network_access": False,
            "exclude_tmpdir_env_var": False,
            "exclude_slash_tmp": False,
        },
        # --- Reasoning/verbosity knobs (spec) ---
        "model_reasoning_effort": args.reasoning_effort,
        "model_reasoning_summary": args.reasoning_summary,
        "model_verbosity": args.verbosity,
        # --- Misc root keys ---
        "profile": state.profile,
        "model_context_window": args.model_context_window or 0,
        "model_max_output_tokens": args.model_max_output_tokens or 0,
        "project_doc_max_bytes": args.project_doc_max_bytes,
        "tui": args.tui,
        "hide_agent_reasoning": args.hide_agent_reasoning,
        "show_raw_agent_reasoning": args.show_raw_agent_reasoning,
        "model_supports_reasoning_summaries": args.model_supports_reasoning_summaries,
        "chatgpt_base_url": args.chatgpt_base_url,
        "experimental_resume": args.experimental_resume,
        "experimental_instructions_file": args.experimental_instructions_file,
        "experimental_use_exec_command_tool": args.experimental_use_exec_command_tool,
        "responses_originator_header_internal_override": args.responses_originator_header_internal_override,
        "preferred_auth_method": args.preferred_auth_method,
        "tools": {"web_search": bool(args.tools_web_search)},
        "disable_response_storage": args.disable_response_storage,
        # --- History ---
        "history": {
            "persistence": "save-all" if not args.no_history else "none",
            "max_bytes": args.history_max_bytes,
        },
        # --- Model providers (seeded with the active one) ---
        "model_providers": {
            state.provider: {
                "name": (
                    "LM Studio"
                    if state.base_url.startswith("http://localhost:1234")
                    else (
                        "Ollama"
                        if state.base_url.startswith("http://localhost:11434")
                        else (
                            "vLLM"
                            if state.base_url.startswith("http://localhost:8000")
                            else (
                                "Text-Gen-WebUI"
                                if state.base_url.startswith("http://localhost:5000")
                                else (
                                    "TGI"
                                    if (
                                        state.base_url.startswith(
                                            "http://localhost:8080"
                                        )
                                        or state.base_url.startswith(
                                            "http://localhost:3000"
                                        )
                                    )
                                    else (
                                        "OpenRouter Local"
                                        if state.base_url.startswith(
                                            "http://localhost:7000"
                                        )
                                        else PROVIDER_LABELS.get(
                                            state.provider, state.provider.capitalize()
                                        )
                                    )
                                )
                            )
                        )
                    )
                ),
                "base_url": state.base_url.rstrip("/"),
                "wire_api": "chat",
                "api_key_env_var": state.env_key,
                # Per-provider network tuning
                "request_max_retries": args.request_max_retries,
                "stream_max_retries": args.stream_max_retries,
                "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
            }
        },
        # --- Profiles (active profile) ---
        "profiles": {
            state.profile: {
                "model": args.model or state.model or "gpt-5",
                "model_provider": state.provider,
                "model_context_window": args.model_context_window or 0,
                "model_max_output_tokens": args.model_max_output_tokens or 0,
                "approval_policy": args.approval_policy,
            }
        },
    }
    if args.azure_api_version:
        cfg["model_providers"][state.provider]["query_params"] = {
            "api-version": args.azure_api_version
        }
    # Add any extra providers/profiles requested via --providers
    extra = getattr(args, "providers_list", []) or []
    for pid in [p for p in extra if p and p != state.provider]:
        # Predefined routes
        if pid.lower() == "lmstudio":
            base_u = DEFAULT_LMSTUDIO
            name = "LM Studio"
        elif pid.lower() == "ollama":
            base_u = DEFAULT_OLLAMA
            name = "Ollama"
        elif pid.lower() == "vllm":
            base_u = DEFAULT_VLLM
            name = PROVIDER_LABELS.get("vllm", "vLLM")
        elif pid.lower() == "tgwui":
            base_u = DEFAULT_TGWUI
            name = PROVIDER_LABELS.get("tgwui", "Text-Gen-WebUI")
        elif pid.lower() == "tgi":
            # Prefer 8080, fall back to 3000
            base_u = DEFAULT_TGI_8080
            name = PROVIDER_LABELS.get("tgi", "TGI")
        elif pid.lower() == "openrouter":
            base_u = DEFAULT_OPENROUTER_LOCAL
            name = PROVIDER_LABELS.get("openrouter", "OpenRouter Local")
        elif pid.lower() in ("jan", "llamafile", "gpt4all", "local"):
            # Use provided base-url or current state base-url as a template
            base_u = args.base_url or state.base_url or DEFAULT_LMSTUDIO
            name = PROVIDER_LABELS.get(pid.lower(), pid.capitalize())
        else:
            base_u = args.base_url or state.base_url or DEFAULT_LMSTUDIO
            name = pid.capitalize()
        cfg["model_providers"][pid] = {
            "name": name,
            "base_url": base_u.rstrip("/"),
            "wire_api": "chat",
            "api_key_env_var": state.env_key,
            "request_max_retries": args.request_max_retries,
            "stream_max_retries": args.stream_max_retries,
            "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
        }
        if args.azure_api_version and pid not in ("lmstudio", "ollama"):
            cfg["model_providers"][pid]["query_params"] = {
                "api-version": args.azure_api_version
            }
        # Add a profile for the extra provider
        cfg["profiles"][pid] = {
            "model": args.model or state.model or "gpt-5",
            "model_provider": pid,
            "model_context_window": args.model_context_window or 0,
            "model_max_output_tokens": args.model_max_output_tokens or 0,
            "approval_policy": args.approval_policy,
        }
    return cfg


def to_toml(cfg: Dict) -> str:
    """Purpose-built TOML emitter for this config shape.
    - Does NOT emit the 'tui' key.
    - Omits empty keys/sections: None, "", "   ", {}, [] are treated as empty.
      Booleans (False) and numbers (0) are NOT considered empty.
    """

    def is_empty(v) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict)):
            return len(v) == 0
        return False

    lines: List[str] = []
    lines.append("# Generated by codex-cli-linker")

    def w(key: str, val):
        # Skip 'tui' entirely and skip empties
        if key == "tui":
            return
        if is_empty(val):
            return
        if isinstance(val, bool):
            sval = "true" if val else "false"
        elif isinstance(val, (int, float)):
            sval = str(val)
        else:
            sval = json.dumps(val)
        lines.append(f"{key} = {sval}")

    # Root scalars
    w("model", cfg.get("model"))
    w("model_provider", cfg.get("model_provider"))
    w("approval_policy", cfg.get("approval_policy"))
    w("sandbox_mode", cfg.get("sandbox_mode"))
    w("file_opener", cfg.get("file_opener"))
    w("model_reasoning_effort", cfg.get("model_reasoning_effort"))
    w("model_reasoning_summary", cfg.get("model_reasoning_summary"))
    w("model_verbosity", cfg.get("model_verbosity"))
    w("model_context_window", cfg.get("model_context_window"))
    w("model_max_output_tokens", cfg.get("model_max_output_tokens"))
    w("project_doc_max_bytes", cfg.get("project_doc_max_bytes"))
    # Intentionally ignored but call w() so the guard path is covered in tests
    w("tui", cfg.get("tui"))
    w("hide_agent_reasoning", cfg.get("hide_agent_reasoning"))
    w("show_raw_agent_reasoning", cfg.get("show_raw_agent_reasoning"))
    w(
        "model_supports_reasoning_summaries",
        cfg.get("model_supports_reasoning_summaries"),
    )
    w("chatgpt_base_url", cfg.get("chatgpt_base_url"))
    w("experimental_resume", cfg.get("experimental_resume"))
    w("experimental_instructions_file", cfg.get("experimental_instructions_file"))
    w(
        "experimental_use_exec_command_tool",
        cfg.get("experimental_use_exec_command_tool"),
    )
    w(
        "responses_originator_header_internal_override",
        cfg.get("responses_originator_header_internal_override"),
    )
    w("preferred_auth_method", cfg.get("preferred_auth_method"))
    w("profile", cfg.get("profile"))
    w("disable_response_storage", cfg.get("disable_response_storage"))

    # tools
    tools = cfg.get("tools") or {}
    # filter empties
    tools_filtered = {k: v for k, v in tools.items() if not is_empty(v)}
    if tools_filtered:
        lines.append("")
        lines.append("[tools]")
        for k, v in tools_filtered.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f"{k} = {json.dumps(v)}")

    # history
    hist = cfg.get("history") or {}
    hist_filtered = {k: v for k, v in hist.items() if not is_empty(v)}
    if hist_filtered:
        lines.append("")
        lines.append("[history]")
        if "persistence" in hist_filtered:
            lines.append(f"persistence = {json.dumps(hist_filtered['persistence'])}")
        if "max_bytes" in hist_filtered:
            lines.append(f"max_bytes = {hist_filtered['max_bytes']}")

    # sandbox_workspace_write
    sww = cfg.get("sandbox_workspace_write") or {}
    sww_filtered = {k: v for k, v in sww.items() if not is_empty(v)}
    if sww_filtered:
        lines.append("")
        lines.append("[sandbox_workspace_write]")
        for k, val in sww_filtered.items():
            if isinstance(val, list):
                if (
                    not val
                ):  # empty list already filtered, but keep safe  # pragma: no cover
                    continue
                arr = ", ".join(json.dumps(x) for x in val if not is_empty(x))
                if arr.strip():
                    lines.append(f"{k} = [ {arr} ]")
            elif isinstance(val, bool):
                lines.append(f"{k} = {'true' if val else 'false'}")
            elif isinstance(val, (int, float)):
                lines.append(f"{k} = {val}")
            else:
                if not is_empty(val):
                    lines.append(f"{k} = {json.dumps(val)}")

    # model_providers
    providers = cfg.get("model_providers") or {}
    for pid, p in providers.items():
        # Filter empty fields
        pf = {k: v for k, v in p.items() if not is_empty(v)}
        # Also remove empty query_params dicts if present (redundant after filtering)
        if "query_params" in pf and is_empty(pf["query_params"]):  # pragma: no cover
            pf.pop("query_params", None)  # pragma: no cover
        if not pf:  # pragma: no cover (pure guard)
            continue
        # Don't emit a section if nothing non-empty remains
        section_lines = []
        for k in ("name", "base_url", "wire_api", "api_key_env_var"):
            if k in pf:
                section_lines.append(f"{k} = {json.dumps(pf[k])}")
        for k in (
            "request_max_retries",
            "stream_max_retries",
            "stream_idle_timeout_ms",
        ):
            if k in pf:
                section_lines.append(f"{k} = {pf[k]}")
        if (
            "query_params" in pf
            and isinstance(pf["query_params"], dict)
            and pf["query_params"]
        ):
            qp_items = ", ".join(
                f"{json.dumps(k)} = {json.dumps(v)}"
                for k, v in pf["query_params"].items()
                if not is_empty(v)
            )
            if qp_items:
                section_lines.append(f"query_params = {{ {qp_items} }}")
        if section_lines:
            lines.append("")
            lines.append(f"[model_providers.{pid}]")
            lines.extend(section_lines)

    # profiles
    profiles = cfg.get("profiles") or {}
    for name, pr in profiles.items():
        prf = {k: v for k, v in pr.items() if not is_empty(v)}
        if not prf:
            continue
        section_lines = []
        for k in (
            "model",
            "model_provider",
            "model_context_window",
            "model_max_output_tokens",
            "approval_policy",
        ):
            if k in prf:
                val = prf[k]
                if isinstance(val, (int, float)):
                    section_lines.append(f"{k} = {val}")
                elif isinstance(
                    val, bool
                ):  # pragma: no cover (bool is int; unreachable)
                    section_lines.append(f"{k} = {'true' if val else 'false'}")
                else:
                    section_lines.append(f"{k} = {json.dumps(val)}")
        if section_lines:
            lines.append("")
            lines.append(f"[profiles.{name}]")
            lines.extend(section_lines)

    out = "\n".join(lines).strip() + "\n"
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def to_json(cfg: Dict) -> str:
    """Serialize ``cfg`` to a pretty-printed JSON string."""
    return json.dumps(cfg, indent=2)


def to_yaml(cfg: Dict) -> str:
    """Tiny YAML emitter to avoid external deps. Good enough for simple config dumps."""

    def dump(obj, indent=0):
        sp = "  " * indent
        if isinstance(obj, dict):
            out = []
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    out.append(f"{sp}{k}:")
                    out.append(dump(v, indent + 1))
                else:
                    if isinstance(v, bool):
                        sval = "true" if v else "false"
                    else:
                        sval = json.dumps(v)
                    out.append(f"{sp}{k}: {sval}")
            return "".join(out)
        elif isinstance(obj, list):
            out = []
            for v in obj:
                if isinstance(v, (dict, list)):
                    out.append(f"{sp}-")
                    out.append(dump(v, indent + 1))
                else:
                    out.append(f"{sp}- {json.dumps(v)}")
            return "".join(out)
        else:
            return f"{sp}{json.dumps(obj)}"

    return dump(cfg) + ""


# =============== Codex helpers ===============


def find_codex_cmd() -> Optional[List[str]]:
    """Locate the codex command or fall back to npx."""
    exe = "codex.cmd" if os.name == "nt" else "codex"
    if shutil.which(exe):
        return [exe]
    if shutil.which("npx"):
        return ["npx", "codex"]
    return None


def ensure_codex_cli() -> List[str]:
    """Ensure Codex CLI is present; attempt a global npm install if missing."""
    cmd = find_codex_cmd()
    if cmd:
        return cmd
    warn("Codex CLI not found on PATH and npx unavailable.")
    npm = shutil.which("npm")
    if npm:
        try:
            subprocess.check_call([npm, "i", "-g", "@openai/codex-cli"])
            ok("Installed @openai/codex-cli globally.")
            cmd = find_codex_cmd()
            if cmd:
                return cmd
        except subprocess.CalledProcessError as e:
            err(f"npm install failed: {e}")
    raise SystemExit("Codex CLI is required. Please install @openai/codex-cli.")


def launch_codex(profile: str) -> int:
    """Launch Codex with the given profile.

    Returns the Codex CLI's exit code and logs the command being executed. The
    function prefers PowerShell on Windows but falls back to ``cmd`` if it's not
    available. On POSIX systems the command is executed directly. ``shlex`` and
    ``subprocess.list2cmdline`` are used to provide accurate shell quoting in
    logs across platforms.
    """

    cmd = ensure_codex_cli()
    full_cmd = cmd + ["--profile", profile]
    info("Launching Codex…")

    if os.name == "nt":
        if shutil.which("powershell"):
            shell_cmd = [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                subprocess.list2cmdline(full_cmd),
            ]
            logging.debug("PowerShell command: %s", " ".join(shell_cmd))
        else:
            shell_cmd = ["cmd", "/c", subprocess.list2cmdline(full_cmd)]
            logging.debug("cmd.exe command: %s", " ".join(shell_cmd))
    else:
        shell_cmd = full_cmd
        logging.debug("POSIX command: %s", shlex.join(full_cmd))

    try:
        result = subprocess.run(shell_cmd)
    except KeyboardInterrupt:
        print()
        warn("Codex terminated by user.")
        return 130

    code = result.returncode
    if code == 0:
        ok(f"Codex exited successfully (code {code}).")
    else:
        err(f"Codex failed with code {code}.")
    return code


# =============== Interactive pickers ===============


def prompt_choice(prompt: str, options: List[str]) -> int:
    """Display a numbered list and return the selected zero-based index."""
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        s = input(f"{prompt} [1-{len(options)}]: ").strip()
        if s.isdigit() and 1 <= int(s) <= len(options):
            return int(s) - 1
        err("Invalid choice.")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Simple interactive yes/no prompt. Returns True for yes, False for no.
    default controls what happens when user just hits Enter.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        s = input(f"{question} {suffix} ").strip().lower()
        if not s:
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        err("Please answer y or n.")


def pick_base_url(state: LinkerState, auto: bool) -> str:
    """Interactively choose or auto-detect the server base URL."""
    if auto:
        return detect_base_url() or state.base_url or DEFAULT_LMSTUDIO
    print()
    print(c("Choose base URL (OpenAI‑compatible):", BOLD))
    opts = [
        f"LM Studio default ({DEFAULT_LMSTUDIO})",
        f"Ollama default ({DEFAULT_OLLAMA})",
        "Custom…",
        "Auto‑detect",
        f"Use last saved ({state.base_url})",
    ]
    idx = prompt_choice("Select", opts)
    choice = opts[idx]
    if choice.startswith("LM Studio"):
        return DEFAULT_LMSTUDIO
    if choice.startswith("Ollama"):
        return DEFAULT_OLLAMA
    if choice.startswith("Custom"):
        return input("Enter base URL (e.g., http://localhost:1234/v1): ").strip()
    if choice.startswith("Auto"):
        return detect_base_url() or input("Enter base URL: ").strip()
    return state.base_url


def pick_model_interactive(base_url: str, last: Optional[str]) -> str:
    """Prompt the user to choose a model from those available on the server."""
    info(f"Querying models from {base_url} …")
    models = list_models(base_url)
    print(c("Available models:", BOLD))
    labels = [m + (c("  (last)", CYAN) if m == last else "") for m in models]
    idx = prompt_choice("Pick a model", labels)
    return models[idx]


# =============== Arg parsing ===============


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments, tracking which were explicitly provided."""
    p = argparse.ArgumentParser(
        description="Codex ⇄ LM Studio / Ollama Linker (Config‑spec compliant)"
    )
    p.formatter_class = argparse.ArgumentDefaultsHelpFormatter
    p.add_argument(
        "-a",
        "--auto",
        action="store_true",
        help="Auto-detect base URL and skip that prompt",
    )
    p.add_argument(
        "-A",
        "--full-auto",
        action="store_true",
        help="Imply --auto and pick the first model with no prompts",
    )
    p.add_argument(
        "-L",
        "--launch",
        action="store_true",
        help="(No-op) Auto launch disabled by design",
    )
    p.add_argument(
        "-Z",
        "--diff",
        action="store_true",
        help="With --dry-run, show a unified diff vs existing files",
    )
    p.add_argument(
        "-Q",
        "--yes",
        action="store_true",
        help="Assume defaults and suppress prompts when inputs are sufficient",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Enable INFO/DEBUG logging"
    )
    p.add_argument(
        "--log-level",
        "--level",
        choices=["debug", "info", "warning", "error"],
        help="Explicit log level (overrides --verbose)",
    )
    p.add_argument("-f", "--log-file", help="Write logs to a file")
    p.add_argument(
        "-J", "--log-json", action="store_true", help="Also log JSON to stdout"
    )
    p.add_argument("-R", "--log-remote", help="POST logs to this HTTP URL")
    p.add_argument(
        "--keychain",
        choices=["none", "auto", "macos", "dpapi", "secretstorage"],
        default="none",
        help="Optionally store --api-key in an OS keychain (never required)",
    )
    p.add_argument(
        "-b", "--base-url", help="Explicit base URL (e.g., http://localhost:1234/v1)"
    )
    p.add_argument("-m", "--model", help="Model id to use (skip model picker)")
    p.add_argument(
        "-P", "--provider", help="Provider id (model_providers.<id>), default deduced"
    )
    p.add_argument(
        "-l",
        "--providers",
        help="Comma-separated provider ids to add (e.g., lmstudio,ollama)",
    )
    p.add_argument("-p", "--profile", help="Profile name, default deduced")
    p.add_argument("-k", "--api-key", help="API key to stash in env (dummy is fine)")
    p.add_argument(
        "-E",
        "--env-key-name",
        default="NULLKEY",
        help="Env var name that holds the API key (default: NULLKEY)",
    )
    p.add_argument("-c", "--config-url", help="URL to JSON file with default args")
    p.add_argument(
        "-i",
        "--model-index",
        type=int,
        help="When auto-selecting, index into the models list (default 0)",
    )
    # Custom linker state file path
    p.add_argument(
        "-x",
        "--state-file",
        help="Path to linker state JSON (default: $CODEX_HOME/linker_config.json)",
    )

    # Config tuning per # Config (choices restricted to spec)
    p.add_argument(
        "-q",
        "--approval-policy",
        default="on-failure",
        choices=["untrusted", "on-failure"],
        help="When to prompt for command approval (spec)",
    )
    p.add_argument(
        "-s",
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write"],
        help="OS sandbox policy (spec)",
    )
    p.add_argument(
        "-o",
        "--file-opener",
        default="vscode",
        choices=["vscode", "vscode-insiders"],
        help="File opener (spec)",
    )
    p.add_argument(
        "-r",
        "--reasoning-effort",
        default="low",
        choices=["minimal", "low"],
        help="model_reasoning_effort (spec)",
    )
    p.add_argument(
        "-u",
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise"],
        help="model_reasoning_summary (spec)",
    )
    p.add_argument(
        "-B",
        "--verbosity",
        default="medium",
        choices=["low", "medium"],
        help="model_verbosity (spec)",
    )
    p.add_argument(
        "-d",
        "--disable-response-storage",
        action="store_true",
        dest="disable_response_storage",
        help="Set disable_response_storage=true (e.g., ZDR orgs)",
    )
    p.add_argument(
        "--enable-response-storage",
        action="store_false",
        dest="disable_response_storage",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "-H",
        "--no-history",
        action="store_true",
        dest="no_history",
        help="Set history.persistence=none",
    )
    p.add_argument(
        "--history", action="store_false", dest="no_history", help=argparse.SUPPRESS
    )
    p.add_argument(
        "-z",
        "--azure-api-version",
        help="If targeting Azure, set query_params.api-version",
    )

    # Numeric knobs & misc
    p.add_argument(
        "-w",
        "--model-context-window",
        type=int,
        default=0,
        help="Context window tokens",
    )
    p.add_argument(
        "-t", "--model-max-output-tokens", type=int, default=0, help="Max output tokens"
    )
    p.add_argument("-D", "--project-doc-max-bytes", type=int, default=1048576)
    p.add_argument("-T", "--tui", default="table")
    p.add_argument("-g", "--hide-agent-reasoning", action="store_true")
    p.add_argument("-G", "--show-raw-agent-reasoning", action="store_true")
    p.add_argument("-Y", "--model-supports-reasoning-summaries", action="store_true")
    p.add_argument("-C", "--chatgpt-base-url", default="")
    p.add_argument("-U", "--experimental-resume", default="")
    p.add_argument("-I", "--experimental-instructions-file", default="")
    p.add_argument("-X", "--experimental-use-exec-command-tool", action="store_true")
    p.add_argument("-O", "--responses-originator-header-internal-override", default="")
    p.add_argument(
        "-M",
        "--preferred-auth-method",
        default="apikey",
        choices=["chatgpt", "apikey"],
    )
    p.add_argument("-W", "--tools-web-search", action="store_true")
    p.add_argument("-N", "--history-max-bytes", type=int, default=0)

    # Per‑provider network knobs
    p.add_argument("-K", "--request-max-retries", type=int, default=4)
    p.add_argument("-S", "--stream-max-retries", type=int, default=10)
    p.add_argument("-e", "--stream-idle-timeout-ms", type=int, default=300_000)

    # Output format toggles (TOML always written unless --dry-run; JSON/YAML only if explicitly requested)
    p.add_argument("-j", "--json", action="store_true", help="Also write config.json")
    p.add_argument("-y", "--yaml", action="store_true", help="Also write config.yaml")
    p.add_argument(
        "-F",
        "--clear",
        action="store_true",
        help="Force clear screen and show banner on start (Windows default is off)",
    )
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print config(s) to stdout without writing files",
    )
    p.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    if argv is None:
        argv = sys.argv[1:]
    ns = p.parse_args(argv)
    # Normalize providers list
    provs = []
    if getattr(ns, "providers", None):
        provs = [p.strip() for p in str(ns.providers).split(",") if p.strip()]
    ns.providers_list = provs
    ns._explicit = {
        a.dest
        for a in p._actions
        if any(
            opt in argv or any(arg.startswith(opt + "=") for arg in argv)
            for opt in a.option_strings
        )
    }
    return ns


def configure_logging(
    verbose: bool,
    log_file: Optional[str] = None,
    log_json: bool = False,
    log_remote: Optional[str] = None,
    log_level: Optional[str] = None,
) -> None:
    """Configure root logger according to CLI flags.

    Existing handlers installed by earlier calls are removed so repeated
    invocations (e.g., tests) do not duplicate log output.
    """

    # Determine base level
    if log_level:
        ll = log_level.lower()
        level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }.get(ll, logging.WARNING)
    else:
        level = logging.DEBUG if verbose else logging.WARNING

    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove handlers added by previous configure_logging calls
    for h in list(logger.handlers):
        if getattr(h, "_added_by_configure_logging", False):
            logger.removeHandler(h)
            h.close()

    fmt = "%(levelname)s: %(message)s"
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(fmt))
    stream._added_by_configure_logging = True
    logger.addHandler(stream)

    if log_json:

        class JSONFormatter(logging.Formatter):
            def format(self, record):
                payload = {
                    "level": record.levelname,
                    "message": record.getMessage(),
                }
                # Include structured fields when provided
                for k in (
                    "event",
                    "provider",
                    "model",
                    "path",
                    "duration_ms",
                    "error_type",
                ):
                    if hasattr(record, k):
                        payload[k] = getattr(record, k)
                return json.dumps(payload)

        json_handler = logging.StreamHandler(sys.stdout)
        json_handler.setFormatter(JSONFormatter())
        json_handler._added_by_configure_logging = True
        logger.addHandler(json_handler)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(fmt))
        fh._added_by_configure_logging = True
        logger.addHandler(fh)

    if log_remote:
        parsed = urllib.parse.urlparse(log_remote)
        host = parsed.netloc
        url = parsed.path or "/"
        if parsed.query:
            url += "?" + parsed.query
        secure = parsed.scheme == "https"

        # Inner HTTP handler (sync); we will wrap with an async buffer.
        inner = logging.handlers.HTTPHandler(host, url, method="POST", secure=secure)

        class BufferedAsyncHandler(logging.Handler):
            def __init__(self, inner_handler: logging.Handler, maxsize: int = 256):
                super().__init__()
                import threading
                import queue

                self.inner = inner_handler
                self.q: "queue.Queue[logging.LogRecord]" = queue.Queue(maxsize=maxsize)
                self._stop = threading.Event()
                self._drops = 0
                self._cv = threading.Condition()

                def worker():
                    while True:
                        with self._cv:
                            while self.q.empty() and not self._stop.is_set():
                                self._cv.wait()
                            if self._stop.is_set() and self.q.empty():
                                break
                        try:
                            rec = self.q.get(block=False)
                        except Exception:
                            continue
                        try:
                            self.inner.emit(rec)
                        except Exception:  # pragma: no cover
                            # Swallow network errors; avoid breaking CLI
                            pass
                        finally:
                            try:
                                self.q.task_done()
                            except Exception:
                                pass

                self._t = threading.Thread(
                    target=worker, name="log-http-worker", daemon=True
                )
                self._t.start()

            def emit(self, record: logging.LogRecord) -> None:
                # In test environments, emit synchronously for determinism
                if os.environ.get("PYTEST_CURRENT_TEST"):
                    try:
                        self.inner.emit(record)
                    except Exception:
                        pass
                    return
                # Non-blocking enqueue. If full, drop oldest and try once more.
                with self._cv:
                    try:
                        self.q.put_nowait(record)
                    except Exception:
                        try:
                            _ = self.q.get_nowait()
                            self._drops += 1
                            self.q.put_nowait(record)
                        except Exception:
                            # queue still full; drop this record
                            self._drops += 1
                    self._cv.notify()

            def close(self) -> None:
                try:
                    self._stop.set()
                    with self._cv:
                        self._cv.notify_all()
                    # Give the worker a brief moment to drain
                    try:
                        self.q.join()
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self.inner.close()
                except Exception:
                    pass
                super().close()

        http_handler = BufferedAsyncHandler(inner)
        http_handler._added_by_configure_logging = True
        logger.addHandler(http_handler)

    for handler in logger.handlers:
        handler.setLevel(level)


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    """Structured log helper. Fields may include provider, model, path, duration_ms, error_type."""
    try:
        logging.getLogger().log(level, event, extra={"event": event, **fields})
    except Exception:
        # Never let logging break CLI flow
        pass


# =============== Optional keychain storage (never required) ===============


def _keychain_backend_auto() -> str:
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "dpapi"
    return "secretstorage"


def store_api_key_in_keychain(backend: str, env_var: str, api_key: str) -> bool:
    """Best-effort storage of API key in OS keychain/credential store.

    Returns True on success. Never raises; logs warnings instead. Not required.
    """
    try:
        if backend == "auto":
            backend = _keychain_backend_auto()

        if backend == "macos":
            if sys.platform != "darwin":
                warn("Keychain backend macos requested on non-macOS; skipping.")
                return False
            svc = f"codex-cli-linker:{env_var}"
            cmd = [
                "security",
                "add-generic-password",
                "-a",
                env_var,
                "-s",
                svc,
                "-w",
                api_key,
                "-U",
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                ok("Stored API key in macOS Keychain.")
                return True
            except Exception as e:
                warn(f"macOS Keychain storage failed: {e}")
                return False

        if backend == "secretstorage":
            try:
                import secretstorage  # type: ignore
            except Exception:
                warn("secretstorage not available; skipping keychain storage.")
                return False
            try:
                bus = secretstorage.dbus_init()
                coll = secretstorage.get_default_collection(bus)
                if coll.is_locked():
                    coll.unlock()
                attrs = {"service": "codex-cli-linker", "account": env_var}
                coll.create_item(
                    f"codex-cli-linker:{env_var}", attrs, api_key, replace=True
                )
                ok("Stored API key in Secret Service.")
                return True
            except Exception as e:  # pragma: no cover
                warn(f"Secret Service storage failed: {e}")
                return False

        if backend == "dpapi":
            if os.name != "nt":
                warn("DPAPI backend requested on non-Windows; skipping.")
                return False
            try:
                import ctypes
                from ctypes import wintypes

                CRED_TYPE_GENERIC = 1
                CRED_PERSIST_LOCAL_MACHINE = 2

                class CREDENTIAL(ctypes.Structure):
                    _fields_ = [
                        ("Flags", wintypes.DWORD),
                        ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR),
                        ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.c_void_p),
                        ("Persist", wintypes.DWORD),
                        ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR),
                        ("UserName", wintypes.LPWSTR),
                    ]

                CredWriteW = ctypes.windll.advapi32.CredWriteW
                CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
                CredWriteW.restype = wintypes.BOOL

                target = f"codex-cli-linker/{env_var}"
                blob = api_key.encode("utf-16le")
                cred = CREDENTIAL()
                cred.Flags = 0
                cred.Type = CRED_TYPE_GENERIC
                cred.TargetName = ctypes.c_wchar_p(target)
                cred.CredentialBlobSize = len(blob)
                cred.CredentialBlob = ctypes.cast(
                    ctypes.create_string_buffer(blob), ctypes.c_void_p
                )
                cred.Persist = CRED_PERSIST_LOCAL_MACHINE
                cred.AttributeCount = 0
                cred.Attributes = None
                cred.UserName = ctypes.c_wchar_p("")

                if not CredWriteW(ctypes.byref(cred), 0):
                    warn("DPAPI CredWriteW failed.")
                    return False
                ok("Stored API key in Windows Credential Manager.")
                return True
            except Exception as e:  # pragma: no cover
                warn(f"DPAPI storage failed: {e}")
                return False

        return False
    except Exception as e:  # pragma: no cover
        warn(f"Keychain storage error: {e}")
        return False


def merge_config_defaults(
    args: argparse.Namespace, defaults: argparse.Namespace
) -> None:
    """Merge values from a remote JSON file into ``args`` when unspecified."""
    if not getattr(args, "config_url", None):
        return
    data, err = http_get_json(args.config_url)
    if not data or not isinstance(data, dict):
        warn(f"Failed to fetch config defaults from {args.config_url}: {err}")
        return
    for k, v in data.items():
        if hasattr(args, k) and getattr(args, k) == getattr(defaults, k):
            setattr(args, k, v)
            if hasattr(args, "_explicit"):
                args._explicit.add(k)


def apply_saved_state(
    args: argparse.Namespace, defaults: argparse.Namespace, state: LinkerState
) -> None:
    """Apply saved preferences unless the user explicitly provided overrides."""
    specified = getattr(args, "_explicit", set())
    for fld in (
        "approval_policy",
        "sandbox_mode",
        "reasoning_effort",
        "reasoning_summary",
        "verbosity",
        "disable_response_storage",
        "no_history",
        "history_max_bytes",
    ):
        if fld not in specified and getattr(args, fld) == getattr(defaults, fld):
            setattr(args, fld, getattr(state, fld))


# =============== Main flow ===============


def main():
    """Entry point for the CLI tool."""
    args = parse_args()
    if getattr(args, "version", False):
        print(get_version())
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
    state_path = (
        Path(args.state_file) if getattr(args, "state_file", None) else LINKER_JSON
    )
    state = LinkerState.load(state_path)
    apply_saved_state(args, defaults, state)

    # Base URL: auto-detect or prompt
    if args.auto:
        base = args.base_url or pick_base_url(state, True)
    else:
        if getattr(args, "yes", False) and not args.base_url:
            err("--yes provided but no --base-url; refusing to prompt.")
            sys.exit(2)
        base = args.base_url or pick_base_url(state, False)
    state.base_url = base

    # Infer a safe default provider from the base URL (localhost:1234 → lmstudio, 11434 → ollama, otherwise 'custom').
    default_provider = (
        "lmstudio"
        if base.startswith("http://localhost:1234")
        else (
            "ollama"
            if base.startswith("http://localhost:11434")
            else (
                "vllm"
                if base.startswith("http://localhost:8000")
                else (
                    "tgwui"
                    if base.startswith("http://localhost:5000")
                    else (
                        "tgi"
                        if (
                            base.startswith("http://localhost:8080")
                            or base.startswith("http://localhost:3000")
                        )
                        else (
                            "openrouter"
                            if base.startswith("http://localhost:7000")
                            else "custom"
                        )
                    )
                )
            )
        )
    )
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
        # Accept exact id or a case-insensitive substring with deterministic tie-break
        target = args.model
        chosen = target
        try:
            models = list_models(state.base_url)
            if target in models:
                chosen = target
            else:
                t = target.lower()
                matches = sorted([m for m in models if t in m.lower()])
                if matches:
                    chosen = matches[0]
                    ok(f"Selected model by substring match: {chosen}")
        except Exception:
            # server may be unreachable; fall back to provided value
            pass
        state.model = chosen
        log_event("model_selected", provider=state.provider, model=state.model)
    elif args.auto and args.model_index is not None:
        try:
            models = list_models(state.base_url)
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

    # Interactive configuration prompts (only when not --auto)
    if not args.auto:
        # APPROVAL POLICY (all allowed by spec)
        ap_opts = ["untrusted", "on-failure"]
        print()
        print(c("Approval policy:", BOLD))
        i = prompt_choice("Choose approval mode", ap_opts)
        args.approval_policy = ap_opts[i]

        # REASONING EFFORT (user-requested full set). Spec allows only minimal|low; others will be clamped.
        re_opts_full = ["minimal", "low", "medium", "high", "auto"]
        print()
        print(c("Reasoning effort:", BOLD))
        i = prompt_choice("Choose reasoning effort", re_opts_full)
        chosen_eff = re_opts_full[i]
        if chosen_eff not in ("minimal", "low"):
            warn(
                "Selected reasoning_effort is outside spec; clamping to nearest supported (low/minimal)."
            )
            chosen_eff = (
                "low" if chosen_eff in ("medium", "high", "auto") else "minimal"
            )
        args.reasoning_effort = chosen_eff

        # REASONING SUMMARY (all allowed by spec)
        rs_opts = ["auto", "concise"]
        print()
        print(c("Reasoning summary:", BOLD))
        i = prompt_choice("Choose reasoning summary", rs_opts)
        args.reasoning_summary = rs_opts[i]

        # VERBOSITY (all allowed by spec)
        vb_opts = ["low", "medium"]
        print()
        print(c("Model verbosity:", BOLD))
        i = prompt_choice("Choose verbosity", vb_opts)
        args.verbosity = vb_opts[i]

        # SANDBOX MODE (all allowed by spec)
        sb_opts = ["read-only", "workspace-write"]
        print()
        print(c("Sandbox mode:", BOLD))
        i = prompt_choice("Choose sandbox mode", sb_opts)
        args.sandbox_mode = sb_opts[i]

        # REASONING VISIBILITY
        print()
        print(c("Reasoning visibility:", BOLD))
        show = True  # default to visible as requested
        show = prompt_yes_no("Show raw agent reasoning?", default=True)
        args.show_raw_agent_reasoning = show
        args.hide_agent_reasoning = not show

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
            cw = try_auto_context_window(state.base_url, state.model)
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

            show_diff(CONFIG_TOML, toml_out, "config.toml")
            if args.json:
                show_diff(CONFIG_JSON, to_json(cfg), "config.json")
            if args.yaml:
                show_diff(CONFIG_YAML, to_yaml(cfg), "config.yaml")
        else:
            print(toml_out, end="")
            if args.json:
                print(to_json(cfg))
            if args.yaml:
                print(to_yaml(cfg))
        info("Dry run: no files were written.")
    else:
        # Ensure home dir exists
        CODEX_HOME.mkdir(parents=True, exist_ok=True)

        # Always write TOML; JSON/YAML only if flags requested. Normalize blank lines and ensure trailing newline.
        t0 = time.time()
        atomic_write_with_backup(CONFIG_TOML, toml_out)
        log_event(
            "write_config",
            provider=state.provider,
            model=state.model,
            path=str(CONFIG_TOML),
            duration_ms=int((time.time() - t0) * 1000),
        )
        ok(f"Wrote {CONFIG_TOML}")

        if args.json:
            t1 = time.time()
            atomic_write_with_backup(CONFIG_JSON, to_json(cfg))
            log_event(
                "write_config",
                provider=state.provider,
                model=state.model,
                path=str(CONFIG_JSON),
                duration_ms=int((time.time() - t1) * 1000),
            )
            ok(f"Wrote {CONFIG_JSON}")

        if args.yaml:
            t2 = time.time()
            atomic_write_with_backup(CONFIG_YAML, to_yaml(cfg))
            log_event(
                "write_config",
                provider=state.provider,
                model=state.model,
                path=str(CONFIG_YAML),
                duration_ms=int((time.time() - t2) * 1000),
            )
            ok(f"Wrote {CONFIG_YAML}")

        # Save linker state for next run (no secrets)
        state.save(state_path)

    # Friendly summary and manual run hint
    print()
    ok(
        f"Configured profile '{state.profile}' using provider '{state.provider}' → {state.base_url} (model: {state.model})"
    )
    # Post-run report
    info("Summary:")
    print(c(f"  target: {CONFIG_TOML}", CYAN))
    try:
        last_bak = max(CONFIG_TOML.parent.glob("config.toml.*.bak"), default=None)
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


if __name__ == "__main__":  # pragma: no cover
    try:  # pragma: no cover
        main()  # pragma: no cover
    except KeyboardInterrupt:  # pragma: no cover
        print()  # pragma: no cover
        warn("Aborted by user.")  # pragma: no cover
