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
import json
import logging
import os
import shutil
import subprocess
import sys
import re
import shlex
import urllib.error
import urllib.request
import concurrent.futures
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    return sys.stdout.isatty() or os.name == "nt"


def c(s: str, color: str) -> str:
    return f"{color}{s}{RESET}" if supports_color() else s


def clear_screen():
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass


def banner():
    art = r"""
                           _      _                  
          /               //     //         /        
 _. __ __/ _  _., --- _. // o   // o ____  /_  _  __ 
(__(_)(_/_</_/ /\_   (__</_<_  </_<_/ / <_/ <_</_/ (_
                                                     
                                                    
"""
    print(c(art, CYAN))


def info(msg: str):
    print(c("ℹ ", BLUE) + msg)


def ok(msg: str):
    print(c("✓ ", GREEN) + msg)


def warn(msg: str):
    print(c("! ", YELLOW) + msg)


def err(msg: str):
    print(c("✗ ", RED) + msg)


# =============== Defaults/paths ===============
DEFAULT_LMSTUDIO = "http://localhost:1234/v1"
DEFAULT_OLLAMA = "http://localhost:11434/v1"
COMMON_BASE_URLS = [DEFAULT_LMSTUDIO, DEFAULT_OLLAMA]

CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
CONFIG_TOML = CODEX_HOME / "config.toml"
CONFIG_JSON = CODEX_HOME / "config.json"
CONFIG_YAML = CODEX_HOME / "config.yaml"
LINKER_JSON = CODEX_HOME / "linker_config.json"


# =============== Data ===============
@dataclass
class LinkerState:
    base_url: str = DEFAULT_LMSTUDIO
    provider: str = "lmstudio"  # provider id in [model_providers.<id>]
    profile: str = "lmstudio"  # profile name in [profiles.<name>]
    api_key: str = "sk-local"  # dummy value; local servers typically ignore
    env_key: str = "NULLKEY"  # DUMMY KEY; never store real secrets here
    model: str = ""  # chosen from /v1/models

    def save(self, path: Path = LINKER_JSON):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        ok(f"Saved linker config: {path}")

    @staticmethod
    def load(path: Path = LINKER_JSON) -> "LinkerState":
        try:
            if path.exists():
                return LinkerState(**json.loads(path.read_text(encoding="utf-8")))
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
        return base, http_get_json(base.rstrip("/") + "/models")

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates))
    futures = [executor.submit(probe, base) for base in candidates]
    try:
        for fut in concurrent.futures.as_completed(futures):
            base, (data, err_) = fut.result()
            if data and isinstance(data, dict) and "data" in data:
                logging.info("Detected server at %s", base)
                ok(f"Detected server: {base}")
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


def backup(path: Path):
    """Backup existing file with a timestamped suffix."""
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        bak = path.with_suffix(f"{path.suffix}.{stamp}.bak")
        try:
            path.replace(bak)
            info(f"Backed up existing {path.name} → {bak.name}")
        except Exception as e:
            warn(f"Backup failed: {e}")


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
        # --- Model providers (only the chosen one is required here) ---
        "model_providers": {
            state.provider: {
                "name": (
                    "LM Studio"
                    if state.base_url.startswith("http://localhost:1234")
                    else (
                        "Ollama"
                        if state.base_url.startswith("http://localhost:11434")
                        else state.provider.capitalize()
                    )
                ),
                "base_url": state.base_url.rstrip("/"),
                "wire_api": "chat",
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
    # w("tui", cfg.get("tui"))  # intentionally not emitted
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
                if not val:  # empty list already filtered, but keep safe
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
        # Also remove empty query_params dicts if present
        if "query_params" in pf and is_empty(pf["query_params"]):
            pf.pop("query_params", None)
        if not pf:
            continue
        # Don't emit a section if nothing non-empty remains
        section_lines = []
        for k in ("name", "base_url", "wire_api"):
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
                elif isinstance(val, bool):
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
    info(f"Querying models from {base_url} …")
    models = list_models(base_url)
    print(c("Available models:", BOLD))
    labels = [m + (c("  (last)", CYAN) if m == last else "") for m in models]
    idx = prompt_choice("Pick a model", labels)
    return models[idx]


# =============== Arg parsing ===============


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Codex ⇄ LM Studio / Ollama Linker (Config‑spec compliant)"
    )
    p.add_argument(
        "--auto", action="store_true", help="Auto‑detect base URL and skip that prompt"
    )
    p.add_argument(
        "--full-auto",
        action="store_true",
        help="Imply --auto and pick the first model with no prompts",
    )
    p.add_argument(
        "--launch", action="store_true", help="(No-op) Auto launch disabled by design"
    )
    p.add_argument("--verbose", action="store_true", help="Enable INFO/DEBUG logging")
    p.add_argument(
        "--base-url", help="Explicit base URL (e.g., http://localhost:1234/v1)"
    )
    p.add_argument("--model", help="Model id to use (skip model picker)")
    p.add_argument(
        "--provider", help="Provider id (model_providers.<id>), default deduced"
    )
    p.add_argument("--profile", help="Profile name, default deduced")
    p.add_argument("--api-key", help="API key to stash in env (dummy is fine)")
    p.add_argument("--config-url", help="URL to JSON file with default args")
    p.add_argument(
        "--model-index",
        type=int,
        help="When auto-selecting, index into the models list (default 0)",
    )

    # Config tuning per # Config (choices restricted to spec)
    p.add_argument(
        "--approval-policy",
        default="on-failure",
        choices=["untrusted", "on-failure"],
        help="When to prompt for command approval (spec)",
    )
    p.add_argument(
        "--sandbox-mode",
        default="workspace-write",
        choices=["read-only", "workspace-write"],
        help="OS sandbox policy (spec)",
    )
    p.add_argument(
        "--file-opener",
        default="vscode",
        choices=["vscode", "vscode-insiders"],
        help="File opener (spec)",
    )
    p.add_argument(
        "--reasoning-effort",
        default="low",
        choices=["minimal", "low"],
        help="model_reasoning_effort (spec)",
    )
    p.add_argument(
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise"],
        help="model_reasoning_summary (spec)",
    )
    p.add_argument(
        "--verbosity",
        default="medium",
        choices=["low", "medium"],
        help="model_verbosity (spec)",
    )
    p.add_argument(
        "--disable-response-storage",
        action="store_true",
        help="Set disable_response_storage=true (e.g., ZDR orgs)",
    )
    p.add_argument(
        "--no-history", action="store_true", help="Set history.persistence=none"
    )
    p.add_argument(
        "--azure-api-version", help="If targeting Azure, set query_params.api-version"
    )

    # Numeric knobs & misc
    p.add_argument(
        "--model-context-window", type=int, default=0, help="Context window tokens"
    )
    p.add_argument(
        "--model-max-output-tokens", type=int, default=0, help="Max output tokens"
    )
    p.add_argument("--project-doc-max-bytes", type=int, default=1048576)
    p.add_argument("--tui", default="table")
    p.add_argument("--hide-agent-reasoning", action="store_true")
    p.add_argument("--show-raw-agent-reasoning", action="store_true")
    p.add_argument("--model-supports-reasoning-summaries", action="store_true")
    p.add_argument("--chatgpt-base-url", default="")
    p.add_argument("--experimental-resume", default="")
    p.add_argument("--experimental-instructions-file", default="")
    p.add_argument("--experimental-use-exec-command-tool", action="store_true")
    p.add_argument("--responses-originator-header-internal-override", default="")
    p.add_argument(
        "--preferred-auth-method", default="apikey", choices=["chatgpt", "apikey"]
    )
    p.add_argument("--tools-web-search", action="store_true")
    p.add_argument("--history-max-bytes", type=int, default=0)

    # Per‑provider network knobs
    p.add_argument("--request-max-retries", type=int, default=4)
    p.add_argument("--stream-max-retries", type=int, default=10)
    p.add_argument("--stream-idle-timeout-ms", type=int, default=300_000)

    # Output format toggles (TOML always written unless --dry-run; JSON/YAML only if explicitly requested)
    p.add_argument("--json", action="store_true", help="Also write config.json")
    p.add_argument("--yaml", action="store_true", help="Also write config.yaml")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config(s) to stdout without writing files",
    )

    return p.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)


def merge_config_defaults(
    args: argparse.Namespace, defaults: argparse.Namespace
) -> None:
    if not getattr(args, "config_url", None):
        return
    data, err = http_get_json(args.config_url)
    if not data or not isinstance(data, dict):
        warn(f"Failed to fetch config defaults from {args.config_url}: {err}")
        return
    for k, v in data.items():
        if hasattr(args, k) and getattr(args, k) == getattr(defaults, k):
            setattr(args, k, v)


# =============== Main flow ===============


def main():
    clear_screen()
    banner()
    args = parse_args()
    if args.full_auto:
        args.auto = True
        if args.model_index is None:
            args.model_index = 0
    configure_logging(args.verbose)
    defaults = parse_args([])
    merge_config_defaults(args, defaults)
    # Hard-disable auto launch regardless of flags
    args.launch = False
    state = LinkerState.load()

    # Base URL: auto-detect or prompt
    base = args.base_url or pick_base_url(state, args.auto)
    state.base_url = base

    # Infer a safe default provider from the base URL (localhost:1234 → lmstudio, 11434 → ollama, otherwise 'custom').
    default_provider = (
        "lmstudio"
        if base.startswith("http://localhost:1234")
        else "ollama" if base.startswith("http://localhost:11434") else "custom"
    )
    state.provider = args.provider or default_provider
    if state.provider == "custom":
        state.provider = (
            input("Provider id to use in model_providers (e.g., myprovider): ").strip()
            or "custom"
        )

    state.profile = args.profile or state.profile or state.provider
    state.api_key = args.api_key or state.api_key or "sk-local"

    # Model selection: interactive unless provided
    if args.model:
        state.model = args.model
    elif args.auto and args.model_index is not None:
        try:
            models = list_models(state.base_url)
            idx = args.model_index if args.model_index >= 0 else 0
            if idx >= len(models):
                idx = 0
            state.model = models[idx]
            ok(f"Auto-selected model: {state.model}")
        except Exception as e:
            err(str(e))
            sys.exit(2)
    else:
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
        backup(CONFIG_TOML)
        CONFIG_TOML.write_text(toml_out, encoding="utf-8")
        ok(f"Wrote {CONFIG_TOML}")

        if args.json:
            backup(CONFIG_JSON)
            CONFIG_JSON.write_text(to_json(cfg), encoding="utf-8")
            ok(f"Wrote {CONFIG_JSON}")

        if args.yaml:
            backup(CONFIG_YAML)
            CONFIG_YAML.write_text(to_yaml(cfg), encoding="utf-8")
            ok(f"Wrote {CONFIG_YAML}")

        # Save linker state for next run (no secrets)
        state.save()

    # Friendly summary and manual run hint
    print()
    ok(
        f"Configured profile '{state.profile}' using provider '{state.provider}' → {state.base_url} (model: {state.model})"
    )
    info("Run Codex manually with:")
    print(c(f"  npx codex --profile {state.profile}", CYAN))
    print(c(f"  codex --profile {state.profile}", CYAN))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Aborted by user.")
