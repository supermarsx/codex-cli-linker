# codex-cli-linker

Generate a ready‑to‑run **Codex CLI** configuration for local OpenAI‑compatible servers like **LM Studio** and **Ollama**.

This small, dependency‑free Python script:

- Detects a local server (LM Studio on `:1234` or Ollama on `:11434`) or uses a custom base URL.
- Fetches available models from `/v1/models` and lets you pick one.
- Emits a modern **`~/.codex/config.toml`** (Codex “# Config” schema) and can optionally emit **JSON** and **YAML** siblings.
- Backs up any existing config (adds `.bak`).
- Stores a tiny linker state (`~/.codex/linker_config.json`) to remember your last choices.
- Can preload defaults from a remote JSON via `--config-url`.
- Preview the would-be files with `--dry-run` (prints to stdout, no writes).

> Works on macOS, Linux, and Windows. No third‑party Python packages required.

---

## Contents
- [Quick start](#quick-start)
- [Installation](#installation)
- [How it works](#how-it-works)
- [Configuration files it writes](#configuration-files-it-writes)
- [Command‑line usage](#command-line-usage)
- [Config keys written](#config-keys-written)
- [Examples](#examples)
- [Environment variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [CI](#ci)
- [Development & code map](#development--code-map)
- [License](#license)

---

## Quick start

```bash
# 1) Clone
git clone https://github.com/<you>/codex-cli-linker
cd codex-cli-linker

# 2) Run interactively (detects server, picks model, writes ~/.codex/config.toml)
python3 codex-cli-linker.py

# 3) Launch Codex with the generated profile (shown at the end of the run)
codex --profile lmstudio      # or: npx codex --profile lmstudio
```

**Non‑interactive:**
```bash
python3 codex-cli-linker.py --auto        # detect server, still prompts for model
python3 codex-cli-linker.py --full-auto   # detect server and first model (no prompts)
```

**Target a specific server/model:**
```bash
python3 codex-cli-linker.py \
  --base-url http://localhost:1234/v1 \
  --provider lmstudio \
  --profile  lmstudio \
  --model    llama-3.1-8b
```

**Also write JSON and/or YAML alongside TOML:**
```bash
python3 codex-cli-linker.py --json --yaml
```

**Show verbose logging for troubleshooting:**
```bash
python3 codex-cli-linker.py --verbose --auto
```

**Preload defaults from a remote JSON:**
```bash
python3 codex-cli-linker.py --config-url https://example.com/defaults.json --auto
```

---

## Installation

This repository ships a single script plus a couple of optional helper scripts:

```
./codex-cli-linker.py          # the tool
./scripts/set_env.sh           # example: set NULLKEY env (macOS/Linux)
./scripts/set_env.bat          # example: set NULLKEY env (Windows)
```

Requirements:
- **Python** 3.8+
- **Codex CLI** (`codex` on PATH, or `npx codex`). If missing, the script will attempt `npm i -g @openai/codex-cli`.
- A local **OpenAI‑compatible server** (LM Studio or Ollama) if you want auto‑detection.

> The tool itself does **not** talk to OpenAI; it only queries your local server’s `/v1/models` to list model IDs.

---

## How it works

1. **Base URL** — Auto‑detects a running server by probing common endpoints:
   - LM Studio: `http://localhost:1234/v1`
   - Ollama: `http://localhost:11434/v1`
   If detection fails, you can select a preset, enter a custom URL, or use your last saved URL.
2. **Model pick** — Calls `GET <base>/models` and lists `data[*].id` for selection.
3. **Config synthesis** — Builds a single in‑memory config object that mirrors the TOML schema (root keys + `[model_providers.<id>]` + `[profiles.<name>]`).
4. **Emission & backup** — Writes `~/.codex/config.toml` (always unless `--dry-run`) and, if requested, `config.json`/`config.yaml`. Any existing file is backed up to `*.bak` first.
5. **State** — Saves `~/.codex/linker_config.json` so next run can preload your last base URL, provider, profile, and model.

---

## Configuration files it writes

By default, files live under **`$CODEX_HOME`** (defaults to `~/.codex`).

- `config.toml`  ← always written unless `--dry-run`
- `config.json`  ← when `--json` is passed
- `config.yaml`  ← when `--yaml` is passed
- `linker_config.json` ← small helper file this tool uses to remember your last choices

> Existing `config.*` are moved to `config.*.bak` before writing.

---

## Command‑line usage

```
python3 codex-cli-linker.py [options]
```

**Connection & selection**
- `--auto` — skip base‑URL prompt and auto‑detect a server
- `--full-auto` — imply `--auto` and pick the first model with no prompts
- `--model-index <N>` — with `--auto`/`--full-auto`, pick model by list index (default 0)
- `--base-url <URL>` — explicit OpenAI‑compatible base URL (e.g., `http://localhost:1234/v1`)
- `--model <ID>` — model id to use (skips interactive model picker)
- `--provider <ID>` — provider key for `[model_providers.<id>]` (e.g., `lmstudio`, `ollama`, `custom`)
- `--profile <NAME>` — profile name for `[profiles.<name>]` (default deduced from provider)

**Behavior & UX**
- `--approval-policy {untrusted,on-failure}` (default: `on-failure`)
- `--sandbox-mode {read-only,workspace-write}` (default: `workspace-write`)
- `--file-opener {vscode,vscode-insiders}` (default: `vscode`)
- `--reasoning-effort {minimal,low}` (default: `low`)
- `--reasoning-summary {auto,concise}` (default: `auto`)
- `--verbosity {low,medium}` (default: `medium`)
- `--hide-agent-reasoning` / `--show-raw-agent-reasoning`

**History & storage**
- `--no-history` — sets `history.persistence=none` (otherwise `save-all`)
- `--history-max-bytes <N>` — sets `history.max_bytes`
- `--disable-response-storage` — sets `disable_response_storage=true`

**Networking & compatibility**
- `--azure-api-version <VER>` — adds `query_params.api-version=<VER>` to the selected provider
- `--request-max-retries <N>` (default: `4`)
- `--stream-max-retries <N>` (default: `10`)
- `--stream-idle-timeout-ms <MS>` (default: `300000`)
- `--chatgpt-base-url <URL>` — optional alternate base for ChatGPT‑authored requests
- `--preferred-auth-method {chatgpt,apikey}` (default: `apikey`)
- `--tools-web-search` — sets `tools.web_search=true`

**Output formats**
- `--json` — also write `~/.codex/config.json`
- `--yaml` — also write `~/.codex/config.yaml`
- `--dry-run` — print configs to stdout without writing files

**Diagnostics**
- `--verbose` — enable INFO/DEBUG logging

> The `--launch` flag is intentionally disabled; the script prints the exact `codex --profile <name>` command instead of auto‑launching.

---

## Config keys written

At a glance, the script writes:

- **Root keys**
  - `model` — chosen model id
  - `model_provider` — provider key (e.g., `lmstudio`, `ollama`)
  - `approval_policy`, `sandbox_mode`, `file_opener`
  - `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`
  - `model_context_window` *(best‑effort auto‑detected; 0 if unknown)*
  - `model_max_output_tokens`
  - `project_doc_max_bytes`
  - `hide_agent_reasoning`, `show_raw_agent_reasoning`, `model_supports_reasoning_summaries`
  - `preferred_auth_method`
  - `tools.web_search`
  - `disable_response_storage`
  - `history.persistence` & `history.max_bytes`

- **`[model_providers.<id>]`** *(only the active one is emitted)*
  - `name` — human label (e.g., "LM Studio", "Ollama")
  - `base_url` — your selected base URL, normalized
  - `wire_api = "chat"` — wire protocol used by Codex
  - `request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`
  - `query_params.api-version` *(when `--azure-api-version` is provided)*

- **`[profiles.<name>]`**
  - `model`, `model_provider`
  - `model_context_window`, `model_max_output_tokens`
  - `approval_policy`

> The tool deliberately **does not store API keys in the file**.

---

## Examples

### Minimal LM Studio profile

```toml
# ~/.codex/config.toml (excerpt)
model = "llama-3.1-8b"
model_provider = "lmstudio"
approval_policy = "on-failure"
sandbox_mode = "workspace-write"
file_opener = "vscode"
model_reasoning_effort = "low"
model_reasoning_summary = "auto"
model_verbosity = "medium"
model_context_window = 0
model_max_output_tokens = 0
project_doc_max_bytes = 1048576

[tools]
web_search = false

[history]
persistence = "save-all"
max_bytes = 0

[model_providers.lmstudio]
name = "LM Studio"
base_url = "http://localhost:1234/v1"
wire_api = "chat"
request_max_retries = 4
stream_max_retries = 10
stream_idle_timeout_ms = 300000

[profiles.lmstudio]
model = "llama-3.1-8b"
model_provider = "lmstudio"
model_context_window = 0
model_max_output_tokens = 0
approval_policy = "on-failure"
```

### Ollama profile

```toml
[model_providers.ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
wire_api = "chat"
request_max_retries = 4
stream_max_retries = 10
stream_idle_timeout_ms = 300000

[profiles.ollama]
model = "llama3"
model_provider = "ollama"
model_context_window = 0
model_max_output_tokens = 0
approval_policy = "on-failure"
```

### Also write JSON/YAML

```bash
python3 codex-cli-linker.py --json --yaml
ls ~/.codex/
# config.toml  config.toml.bak  config.json  config.yaml  linker_config.json
```

---

## Environment variables

- `CODEX_HOME` — overrides the config directory (default: `~/.codex`).
- `NULLKEY` — a placeholder env var this tool initializes to `"nullkey"` so configs never need to include secrets.
  - Optional helper scripts:
    - macOS/Linux: `source scripts/set_env.sh`
    - Windows: `scripts\set_env.bat`

> If your provider requires a key, prefer exporting it in your shell and letting Codex read it from the environment rather than writing it to disk.

---

## Troubleshooting

- **“No server auto‑detected.”**  
  Ensure LM Studio’s local server is running (check *Developer → Local Server* is enabled) or that Ollama is running. Otherwise pass `--base-url`.

- **“Models list is empty.”**  
  Your server didn’t return anything from `GET /v1/models`. Verify the endpoint and that at least one model is downloaded/available.

- **Network errors**  
  Use `--request-max-retries`, `--stream-max-retries`, or `--stream-idle-timeout-ms` to tune resilience for flaky setups.

- **History & storage**  
  If you’re in a restricted environment, add `--disable-response-storage` and/or `--no-history` when generating the config.

- **Azure/OpenAI compatibility**
  When talking to Azure‑hosted compatible endpoints, pass `--azure-api-version <YYYY-MM-DD>` to set `query_params.api-version`.

---

## CI

GitHub Actions run four jobs:

- **lint** — `ruff check .`
- **format** — `black --check .`
- **test** — `pytest`
- **build** — `python -m build` on Ubuntu, macOS, and Windows

`lint`, `format`, and `test` run in parallel and fail independently. `build` runs only after all three succeed.

---

## Development & code map

Single‑file tool: `codex-cli-linker.py`

Key modules & functions:
- **`LinkerState`** — persists last base URL, provider, profile, model (`~/.codex/linker_config.json`).
- **Detection** — `detect_base_url()`, `list_models()`
- **Pickers** — `pick_base_url()`, `pick_model_interactive()`
- **Config build** — `build_config_dict()` (single source of truth), emitters: `to_toml()`, `to_json()`, `to_yaml()`
- **Codex CLI integration** — `find_codex_cmd()`, `ensure_codex_cli()`

Run locally:
```bash
python3 -m pip install --upgrade pip
python3 codex-cli-linker.py --auto
```

Contributions welcome! Please open issues/PRs with logs (`-v` output where relevant) and a description of your environment.

---

## License

MIT © 2025 Mariana  
See [`license.md`](license.md).

