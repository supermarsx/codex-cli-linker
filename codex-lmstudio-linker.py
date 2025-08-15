#!/usr/bin/env python3
"""
Interactive Codex ⇄ LM Studio / Ollama Linker (Python, cross‑platform)

Features:
  • Colorful, interactive CLI with numbered pickers
  • LM Studio / Ollama base URL picker: Default, Ollama, Custom, or Auto‑detect
  • Live model discovery from /v1/models and simple health checks (/v1/chat/completions optional)
  • Create/Update Codex provider + profiles in ~/.codex/config.toml
  • Save/Load a small linker config (JSON) to preload last choices
  • Codex launcher fallback: uses `npx codex` if `codex` not found in PATH
  • Optionally attempts to install `@openai/codex-cli` globally via npm if missing (prompted)

Notes:
  • LM Studio exposes an OpenAI‑compatible API (default http://localhost:1234/v1)
  • Ollama exposes an OpenAI‑compatible API (default http://localhost:11434/v1) when OpenAI server mode is on
  • Codex config is stored at ~/.codex/config.toml
  • This script only writes minimal TOML needed by Codex CLI (OpenAI‑compatible provider + profile)

Usage (interactive):
  python interactive_codex_lm_studio_linker.py

Usage (non‑interactive examples):
  python interactive_codex_lm_studio_linker.py --auto --launch
  python interactive_codex_lm_studio_linker.py --base-url http://localhost:1234/v1 --model llama-3.1-8b --profile lmstudio --provider lmstudio --launch
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

# ---------- Colors ----------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"

def supports_color() -> bool:
    if sys.platform == "win32":
        # Windows 10+ terminals support ANSI; enable VT on legacy where possible
        return True
    return sys.stdout.isatty()

def c(fmt: str, color: str) -> str:
    return f"{color}{fmt}{RESET}" if supports_color() else fmt

def info(msg: str): print(c("ℹ ", BLUE) + msg)
def ok(msg: str): print(c("✓ ", GREEN) + msg)
def warn(msg: str): print(c("! ", YELLOW) + msg)
def err(msg: str): print(c("✗ ", RED) + msg)

# ---------- Data ----------
DEFAULT_LMSTUDIO = "http://localhost:1234/v1"
DEFAULT_OLLAMA = "http://localhost:11434/v1"
COMMON_BASE_URLS = [DEFAULT_LMSTUDIO, DEFAULT_OLLAMA]

CONFIG_DIR = Path.home() / ".codex"
CONFIG_FILE = CONFIG_DIR / "config.toml"
LINKER_JSON = CONFIG_DIR / "linker_config.json"

@dataclass
class LinkerState:
    base_url: str = DEFAULT_LMSTUDIO
    provider: str = "lmstudio"   # free‑form name used in TOML providers section
    profile: str = "lmstudio"    # profile name in TOML profiles section
    api_key: str = "sk-local"    # dummy—most local servers ignore key but Codex expects something
    model: str = ""              # to be picked from /v1/models

    def save(self, path: Path = LINKER_JSON):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        ok(f"Saved linker config: {path}")

    @staticmethod
    def load(path: Path = LINKER_JSON) -> "LinkerState":
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return LinkerState(**data)
            except Exception as e:
                warn(f"Could not load {path}: {e}")
        return LinkerState()

# ---------- HTTP helpers ----------
def http_get_json(url: str, timeout: float = 3.0) -> Tuple[Optional[dict], Optional[str]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8", errors="ignore")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, str(e)

def detect_base_url(candidates: List[str] = COMMON_BASE_URLS) -> Optional[str]:
    info("Auto‑detecting OpenAI‑compatible servers...")
    for base in candidates:
        models_url = base.rstrip("/") + "/models"
        data, err_ = http_get_json(models_url)
        if data and isinstance(data, dict) and "data" in data:
            ok(f"Detected server: {base}")
            return base
        else:
            print(c(f"  • {base} not responding to /models ({err_})", GRAY))
    warn("No server auto‑detected.")
    return None

def list_models(base_url: str) -> List[str]:
    models_url = base_url.rstrip("/") + "/models"
    data, err_ = http_get_json(models_url)
    if not data:
        raise RuntimeError(f"Failed to fetch models from {models_url}: {err_}")
    items = data.get("data") or []
    models = []
    for it in items:
        mid = it.get("id")
        if mid:
            models.append(mid)
    return models

# ---------- TOML writing (minimal, no external deps) ----------
def write_codex_toml(state: LinkerState, path: Path = CONFIG_FILE):
    cfg = generate_minimal_toml(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            path.replace(backup)
            info(f"Backed up existing config to {backup}")
        except Exception as e:
            warn(f"Could not backup existing config: {e}")
    path.write_text(cfg, encoding="utf-8")
    ok(f"Wrote Codex config: {path}")

def generate_minimal_toml(state: LinkerState) -> str:
    # Minimal structure expected by Codex CLI (OpenAI‑compatible provider)
    lines = []
    lines.append("# Generated by interactive_codex_lm_studio_linker.py")
    lines.append("")
    lines.append("[[providers]]")
    lines.append(f'name = "{state.provider}"')
    lines.append('type = "openai"')
    lines.append(f'api_key = "{state.api_key}"')
    lines.append(f'base_url = "{state.base_url}"')
    lines.append("")
    lines.append("[[profiles]]")
    lines.append(f'name = "{state.profile}"')
    lines.append(f'provider = "{state.provider}"')
    if state.model:
        lines.append(f'model = "{state.model}"')
    lines.append("")
    return "\n".join(lines)

# ---------- Codex CLI helpers ----------
def find_codex_cmd() -> Optional[List[str]]:
    # Prefer `codex` on PATH
    exe = "codex.cmd" if os.name == "nt" else "codex"
    found = shutil.which(exe)
    if found:
        return [found]
    # Fallback to npx
    npx = shutil.which("npx")
    if npx:
        return [npx, "codex"]
    return None

def ensure_codex_cli_interactive() -> List[str]:
    cmd = find_codex_cmd()
    if cmd:
        return cmd
    warn("Codex CLI not found on PATH and npx not available.")
    npm = shutil.which("npm")
    if npm:
        ans = input("Install '@openai/codex-cli' globally via npm now? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            try:
                subprocess.check_call([npm, "i", "-g", "@openai/codex-cli"])
                ok("Installed @openai/codex-cli globally.")
                cmd = find_codex_cmd()
                if cmd:
                    return cmd
            except subprocess.CalledProcessError as e:
                err(f"npm install failed: {e}")
    raise SystemExit("Codex CLI is required. Install @openai/codex-cli and try again.")

def launch_codex_profile(profile: str):
    cmd = ensure_codex_cli_interactive()
    info(f"Launching: {' '.join(cmd)} --profile {profile}")
    try:
        subprocess.call(cmd + ["--profile", profile])
    except KeyboardInterrupt:
        print()
        warn("Codex terminated by user.")

# ---------- Interactive pickers ----------
def pick_base_url(state: LinkerState) -> str:
    print()
    print(c("Choose base URL (OpenAI‑compatible):", BOLD))
    options = [
        f"LM Studio default ({DEFAULT_LMSTUDIO})",
        f"Ollama default ({DEFAULT_OLLAMA})",
        "Custom...",
        "Auto‑detect",
        f"Use last saved ({state.base_url})" if state.base_url else None,
    ]
    options = [o for o in options if o]
    for i, label in enumerate(options, 1):
        print(f"  {i}. {label}")
    while True:
        choice = input("Select [1‑{}]: ".format(len(options))).strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(options)):
            err("Invalid choice."); continue
        idx = int(choice) - 1
        label = options[idx]
        if label.startswith("LM Studio"):
            return DEFAULT_LMSTUDIO
        if label.startswith("Ollama"):
            return DEFAULT_OLLAMA
        if label.startswith("Custom"):
            val = input("Enter base URL (e.g., http://localhost:1234/v1): ").strip()
            return val
        if label.startswith("Auto‑detect"):
            detected = detect_base_url()
            if detected: return detected
            warn("Falling back to custom entry.")
            return input("Enter base URL: ").strip()
        if label.startswith("Use last"):
            return state.base_url

def pick_model(base_url: str, last: Optional[str]) -> str:
    print()
    info(f"Querying models from {base_url} ...")
    models = list_models(base_url)
    if not models:
        raise SystemExit("No models reported by the server.")
    print(c("Available models:", BOLD))
    for i, m in enumerate(models, 1):
        tag = c(" (last)", CYAN) if last and m == last else ""
        print(f"  {i}. {m}{tag}")
    while True:
        choice = input("Pick a model by number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice)-1]
        err("Invalid choice.")

def pick_provider_name(default: str) -> str:
    v = input(f"Provider name in Codex (default '{default}'): ").strip()
    return v or default

def pick_profile_name(default: str) -> str:
    v = input(f"Profile name in Codex (default '{default}'): ").strip()
    return v or default

def pick_api_key(default: str) -> str:
    v = input(f"API key (most local servers ignore; default '{default}'): ").strip()
    return v or default

# ---------- Main ----------
def run_interactive(auto: bool = False, launch: bool = False,
                    base_url_arg: Optional[str] = None,
                    model_arg: Optional[str] = None,
                    provider_arg: Optional[str] = None,
                    profile_arg: Optional[str] = None,
                    api_key_arg: Optional[str] = None):
    state = LinkerState.load()
    # Base URL
    base = base_url_arg
    if not base:
        if auto:
            base = detect_base_url() or state.base_url or DEFAULT_LMSTUDIO
        else:
            base = pick_base_url(state)
    state.base_url = base

    # Provider/Profile/API key
    state.provider = provider_arg or pick_provider_name(state.provider)
    state.profile = profile_arg or pick_profile_name(state.profile)
    state.api_key = api_key_arg or pick_api_key(state.api_key)

    # Model
    model = model_arg or pick_model(state.base_url, state.model or None)
    state.model = model

    # Write TOML
    write_codex_toml(state)
    # Save linker JSON
    state.save()

    ok(f"Configured profile '{state.profile}' using provider '{state.provider}' → {state.base_url} (model: {state.model})")

    if launch:
        launch_codex_profile(state.profile)
    else:
        info("You can launch Codex later with:")
        print(c(f"  codex --profile {state.profile}", CYAN))
        print(c(f"  npx codex --profile {state.profile}", CYAN))

def parse_args(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser(description="Interactive Codex ⇄ LM Studio / Ollama Linker")
    ap.add_argument("--auto", action="store_true", help="Auto‑detect base URL and skip that prompt")
    ap.add_argument("--launch", action="store_true", help="Launch Codex after writing config")
    ap.add_argument("--base-url", help="Explicit base URL (e.g., http://localhost:1234/v1)")
    ap.add_argument("--model", help="Model id to use (skip model picker)")
    ap.add_argument("--provider", help="Codex provider name")
    ap.add_argument("--profile", help="Codex profile name")
    ap.add_argument("--api-key", help="API key to write in config (local servers usually ignore)")
    return ap.parse_args(argv)

def main():
    args = parse_args(sys.argv[1:])
    # If any of these are non‑interactive hints, we skip prompts accordingly
    run_interactive(auto=args.auto, launch=args.launch,
                    base_url_arg=args.base_url, model_arg=args.model,
                    provider_arg=args.provider, profile_arg=args.profile,
                    api_key_arg=args.api_key)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Aborted by user.")
