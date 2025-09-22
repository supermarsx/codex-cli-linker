# codex-cli-linker

[![CI](https://github.com/supermarsx/codex-cli-linker/actions/workflows/ci.yml/badge.svg)](https://github.com/supermarsx/codex-cli-linker/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/pypi/v/codex-cli-linker)](https://pypi.org/project/codex-cli-linker/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/codex-cli-linker?logo=pypi)](https://pypi.org/project/codex-cli-linker/)
[![PyPI Total Downloads](https://img.shields.io/pepy/dt/codex-cli-linker?logo=pypi)](https://pepy.tech/project/codex-cli-linker)
[![Coverage](./coverage.svg)](./coverage.svg)
[![Downloads](https://img.shields.io/github/downloads/supermarsx/codex-cli-linker/total?logo=github)](https://github.com/supermarsx/codex-cli-linker/releases)
[![Stars](https://img.shields.io/github/stars/supermarsx/codex-cli-linker?logo=github)](https://github.com/supermarsx/codex-cli-linker/stargazers)
[![Forks](https://img.shields.io/github/forks/supermarsx/codex-cli-linker?logo=github)](https://github.com/supermarsx/codex-cli-linker/network/members)
[![Watchers](https://img.shields.io/github/watchers/supermarsx/codex-cli-linker?logo=github)](https://github.com/supermarsx/codex-cli-linker/watchers)
[![Issues](https://img.shields.io/github/issues/supermarsx/codex-cli-linker)](https://github.com/supermarsx/codex-cli-linker/issues)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/supermarsx/codex-cli-linker)](https://github.com/supermarsx/codex-cli-linker/graphs/commit-activity)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python%203.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](./license.md)

Generate a ready‑to‑run **Codex CLI** configuration for local OpenAI‑compatible servers like **LM Studio** and **Ollama**.

This small, dependency‑free Python script:

- Detects a local server (LM Studio on `:1234` or Ollama on `:11434`) or uses a custom base URL.
- Fetches available models from `/v1/models` and lets you pick one.
- Emits a modern **`~/.codex/config.toml`** (Codex “# Config” schema) and can optionally emit **JSON** and **YAML** siblings.
- Backs up any existing config (adds `.bak`).
- Stores a tiny linker state (`~/.codex/linker_config.json` or `./.codex-linker.json` when using workspace override) to remember your last choices.
- Can preload defaults from a remote JSON via `--config-url`.
- Preview the would-be files with `--dry-run` (prints to stdout, no writes).

## Features

- Auto-detects local OpenAI-compatible servers (LM Studio, Ollama, vLLM, Text‑Gen‑WebUI OpenAI plugin, TGI shim, OpenRouter local) and normalizes base URLs.
- Interactive and non-interactive flows: `--auto`, `--full-auto`, or fully manual.
- Model discovery from `/v1/models` with a simple picker or direct `--model`/`--model-index`.
- Produces TOML by default and optional JSON/YAML mirrors to keep schema parity.
- Centralized schema shaping via a single `build_config_dict()`—no duplicated logic.
- Creates safe backups (`*.bak`) before overwriting existing configs.
- Remembers last choices in `~/.codex/linker_config.json` (or `./.codex-linker.json` when using workspace override) for faster repeat runs.
- First-class cross‑platform UX: clean colors, concise messages, no auto‑launch side effects.
- Diagnostic tooling: verbose logging, file logging, JSON logs, and remote HTTP log export.
- Tunable retry/timeout parameters for flaky networks; Azure-style `api-version` support.
- Security-aware: never writes API keys to disk; favors env vars (`NULLKEY` placeholder by default).
  - Optional: `--keychain` can store your `--api-key` in the OS keychain (macOS Keychain, Windows DPAPI/Credential Manager, Linux Secret Service via `secretstorage`, GNU pass, or integrate with Bitwarden/1Password CLIs). The config still references the env var; secrets are never written to config files.
- Compatible with Codex CLI approvals, sandbox, and history controls without post-editing.

> Works on macOS, Linux, and Windows. No third‑party Python packages required.


## Contents
- [Quick start](#quick-start)
- [Installation](#installation)
- [How it works](#how-it-works)
- [Configuration files it writes](#configuration-files-it-writes)
- [Command-line usage](#command-line-usage)
- [Docker](#docker)
- [Config keys written](#config-keys-written)
- [Examples](#examples)
- [Environment variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Windows Defender False Positive](#windows-defender-false-positive)
- [Changelog](#changelog)
- [Development](#development)
- [License](#license)


## Quick start

Pick one of the three options below.

### A) Clone and run
```bash
git clone https://github.com/supermarsx/codex-cli-linker
cd codex-cli-linker
python3 codex-cli-linker.py           # interactive
```
Non‑interactive examples:
```bash
python3 codex-cli-linker.py --auto        # detect server, still prompts for model
python3 codex-cli-linker.py --full-auto   # detect server and first model (no prompts)
```

### B) Standalone executable
Download from Releases:
- Windows x64: codex-cli-linker-windows-x64.exe
- macOS x64:   codex-cli-linker-macos-x64
- macOS arm64: codex-cli-linker-macos-arm64
- Linux x64:   codex-cli-linker-linux-x64
- Linux arm64: codex-cli-linker-linux-arm64

Direct download buttons (latest assets):

<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-windows-x64.exe"><img alt="Download Windows x64" src="https://img.shields.io/badge/⬇%20Windows-x64-0b5fff?logo=windows&logoColor=white" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-macos-x64"><img alt="Download macOS x64" src="https://img.shields.io/badge/⬇%20macOS-x64-0b5fff?logo=apple&logoColor=white" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-linux-x64"><img alt="Download Linux x64" src="https://img.shields.io/badge/⬇%20Linux-x64-0b5fff?logo=linux&logoColor=white" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-macos-arm64"><img alt="Download macOS arm64" src="https://img.shields.io/badge/⬇%20macOS-arm64-0b5fff?logo=apple&logoColor=white" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-linux-arm64"><img alt="Download Linux arm64" src="https://img.shields.io/badge/⬇%20Linux-arm64-0b5fff?logo=linux&logoColor=white" /></a>

Or fetch via curl (latest):

```bash
# macOS
curl -L -o codex-cli-linker-macos-x64 \
  https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-macos-x64 \
  && chmod +x codex-cli-linker-macos-x64 \
  && ./codex-cli-linker-macos-x64 --auto

# Linux
curl -L -o codex-cli-linker-linux-x64 \
  https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-linux-x64 \
  && chmod +x codex-cli-linker-linux-x64 \
  && ./codex-cli-linker-linux-x64 --auto

# Windows (PowerShell or CMD with curl available)
curl -L -o codex-cli-linker-windows-x64.exe ^
  https://github.com/supermarsx/codex-cli-linker/releases/latest/download/codex-cli-linker-windows-x64.exe && \
  .\codex-cli-linker-windows-x64.exe --auto
```

Then run it (example):
```bash
# macOS/Linux once after download
chmod +x ./codex-cli-linker-*-x64
./codex-cli-linker-*-x64 --auto

# Windows
./codex-cli-linker-windows-x64.exe --auto
```

### C) PyPI (pipx or pip)
```bash
# Recommended: isolated install
pipx install codex-cli-linker
codex-cli-linker.py --auto

# Or user install via pip
python3 -m pip install --user codex-cli-linker
codex-cli-linker.py --auto
```

### D) Homebrew (macOS / Linux)
```bash
brew tap supermarsx/codex-cli-linker https://github.com/supermarsx/codex-cli-linker
brew install supermarsx/codex-cli-linker/codex-cli-linker
codex-cli-linker --auto
```

### E) Scoop (Windows)
```powershell
scoop bucket add codex-cli-linker https://github.com/supermarsx/codex-cli-linker
scoop install codex-cli-linker
codex-cli-linker --auto
```

After generating files, launch Codex with the printed profile:
```bash
npx codex --profile lmstudio   # or: codex --profile lmstudio
```

More examples:
```bash
# Target a specific server/model
python3 codex-cli-linker.py \
  --base-url http://localhost:1234/v1 \
  --provider lmstudio \
  --profile  lmstudio \
  --model    llama-3.1-8b         # or: a substring like --model llama-3.1

# Also write JSON and/or YAML alongside TOML
python3 codex-cli-linker.py --json --yaml

# Preview config without writing files
python3 codex-cli-linker.py --dry-run --auto

# Troubleshooting verbosity
python3 codex-cli-linker.py --verbose --auto

# Log to a file / emit JSON logs / send logs remotely
python3 codex-cli-linker.py --log-file linker.log
python3 codex-cli-linker.py --log-json
python3 codex-cli-linker.py --log-remote http://example.com/log

# Run preflight diagnostics (connectivity, permissions)
python3 codex-cli-linker.py --doctor --base-url http://localhost:1234/v1

# Doctor with feature probing
python3 codex-cli-linker.py --doctor --doctor-detect-features --base-url http://localhost:1234/v1

# Preload defaults from a remote JSON
python3 codex-cli-linker.py --config-url https://example.com/defaults.json --auto
```

### OpenAI default linking mode

Create a profile that targets the hosted OpenAI API (no local server required). You can either select it in the interactive base URL picker or use flags:

```bash
# Non-interactive example
python3 codex-cli-linker.py --provider openai --auto --yes \
  --model gpt-4o-mini --env-key-name OPENAI_API_KEY
```

Two OpenAI auth modes are supported; both set `provider=openai`:

```bash
# API-key mode (preferred_auth_method=apikey)
python3 codex-cli-linker.py --openai-api --auto --yes --model gpt-4o-mini

# ChatGPT mode (preferred_auth_method=chatgpt)
python3 codex-cli-linker.py --openai-gpt --auto --yes --model gpt-4o-mini
```

In interactive mode, choose "OpenAI API (https://api.openai.com/v1)" when asked for the base URL.
When provider is OpenAI, you'll be prompted to choose between API key and ChatGPT auth. If you choose API key mode, the tool offers to set/update your OPENAI_API_KEY in `~/.codex/auth.json` during the flow.

### Set only OPENAI_API_KEY and quit

If you just want to set an `OPENAI_API_KEY` in `~/.codex/auth.json` and exit (no config writes):

```bash
# Interactive prompt (input hidden)
python3 codex-cli-linker.py --set-openai-key

# Non-interactive: pass the key
python3 codex-cli-linker.py --set-openai-key --api-key sk-...
```

Notes:
- Writes `~/.codex/auth.json` and creates a timestamped backup if it exists.
- Never commits user configs; keep `auth.json` private (contains secrets).
- No other files are modified in this mode.

### Profile management

You can manage profiles before writing config:

```bash
# Interactive add/remove/edit of profiles during the run
python3 codex-cli-linker.py --manage-profiles

# Safety: prevent accidental overwrite of an existing [profiles.<name>]
# (the tool will prompt unless --yes is used)
python3 codex-cli-linker.py --profile myprofile   # will prompt if exists
python3 codex-cli-linker.py --profile myprofile --overwrite-profile  # allow overwrite

# Merge only the generated profiles into an existing config.toml (preserves other profiles)
python3 codex-cli-linker.py --merge-profiles --profile myprofile --model llama-3.1-8b
```

### MCP servers

Configure external MCP servers under the top-level `mcp_servers` key (not `mcpServers`). You can manage them interactively or pass a JSON blob:

```bash
# Interactive management
python3 codex-cli-linker.py --manage-mcp

# Non-interactive via JSON (example entry named "search")
python3 codex-cli-linker.py --auto --yes --model gpt-4o-mini --provider openai \
  --mcp-json '{
    "search": {
      "command": "npx",
      "args": ["-y", "mcp-server"],
      "env": {"API_KEY": "value"},
      "startup_timeout_ms": 20000
    }
  }'
```

Config structure produced:

```toml
[mcp_servers.search]
command = "npx"
args = ["-y", "mcp-server"]
startup_timeout_ms = 20000 # optional; default is 10000 when omitted

[mcp_servers.search.env]
API_KEY = "value"
```


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

### Install from PyPI

If you prefer a package install (no cloning needed):

```bash
# Recommended: isolated install via pipx
pipx install codex-cli-linker

# Or user install via pip
python3 -m pip install --user codex-cli-linker

# Then run (the script is installed on your PATH)
codex-cli-linker.py --auto            # or just: codex-cli-linker.py
```

### Install via Homebrew

Homebrew installs the tool in a virtual environment and exposes the `codex-cli-linker` entry point:

```bash
brew tap supermarsx/codex-cli-linker https://github.com/supermarsx/codex-cli-linker
brew install supermarsx/codex-cli-linker/codex-cli-linker
codex-cli-linker --auto
```

Upgrade when a new release ships:

```bash
brew update
brew upgrade codex-cli-linker
```

See [docs/homebrew.md](docs/homebrew.md) for tap maintenance notes.

### Install via Scoop (Windows)

Scoop installs the single-file executable and shims it onto your PATH:

```powershell
scoop bucket add codex-cli-linker https://github.com/supermarsx/codex-cli-linker
scoop install codex-cli-linker
codex-cli-linker --auto
```

Upgrade with:

```powershell
scoop update codex-cli-linker
```

See [docs/scoop.md](docs/scoop.md) for manifest maintenance notes.

Notes:
- PyPI installs the single script; there is no Python package import. Run the script by name.
- On Windows PowerShell, use `py -m pip install codex-cli-linker` then run `codex-cli-linker.py`.
- Homebrew keeps the package under `$(brew --cellar)/codex-cli-linker/<version>` and exposes the `codex-cli-linker` entry point on your PATH.
- Scoop keeps shims in `~/scoop/shims/` while the app lives under `~/scoop/apps/codex-cli-linker/current`.


## How it works

1. **Base URL** — Auto‑detects a running server by probing common endpoints:
   - LM Studio: `http://localhost:1234/v1`
   - Ollama: `http://localhost:11434/v1`
   If detection fails, you can select a preset, enter a custom URL, or use your last saved URL.
2. **Model pick** — Calls `GET <base>/models` and lists `data[*].id` for selection.
3. **Config synthesis** — Builds a single in‑memory config object that mirrors the TOML schema (root keys + `[model_providers.<id>]` + `[profiles.<name>]`).
4. **Emission & backup** — Writes `~/.codex/config.toml` (always unless `--dry-run`) and, if requested, `config.json`/`config.yaml`. Any existing file is backed up to `*.bak` first.
5. **State** — Saves `~/.codex/linker_config.json` so next run can preload your last base URL, provider, profile, and model.


## Configuration files it writes

By default, files live under **`$CODEX_HOME`** (defaults to `~/.codex`).

- `config.toml`  ← always written unless `--dry-run`
- `config.json`  ← when `--json` is passed
- `config.yaml`  ← when `--yaml` is passed
- `linker_config.json` ← small helper file this tool uses to remember your last choices

> Existing `config.*` are moved to `config.*.bak` before writing.


## Command-line usage

```
python3 codex-cli-linker.py [options]
```

Tip: All options have short aliases (e.g., `-a` for `--auto`). Run `-h` to see the full list.

Additional handy short aliases:
- `-mp/--merge-profiles`, `-mc/--merge-config`, `-mO/--merge-overwrite`
- `-mm/--manage-mcp`, `-mj/--mcp-json`
- `-Na/--network-access`
- `-Et/--exclude-tmpdir-env-var`
- `-Es/--exclude-slash-tmp`, `-ES/--no-exclude-slash-tmp`
- `-Wr/--writable-roots`
- `-wa/--wire-api`
- `-Hh/--http-header`, `-He/--env-http-header`
- `-Nt/--notify`, `-In/--instructions`, `-Tp/--trust-project`
- `-Tn/--tui-notifications`, `-Tt/--tui-notification-types`
- `-oa/--openai`, `-oA/--openai-api`, `-og/--openai-gpt`
- `-dr/--doctor`, `-cu/--check-updates`, `-nuc/--no-update-check`
- `-ll/--log-level`, `-rc/--remove-config`, `-rN/--remove-config-no-bak`, `-db/--delete-all-backups`, `-dc/--confirm-delete-backups`
- `-ws/--workspace-state`, `-oc/--open-config`, `-sK/--set-openai-key`, `-kc/--keychain`, `-op/--overwrite-profile`, `-mP/--manage-profiles`

**Connection & selection**
- `--auto` — skip base‑URL prompt and auto‑detect a server
- `--full-auto` — imply `--auto` and pick the first model with no prompts
- `--model-index <N>` — with `--auto`/`--full-auto`, pick model by list index (default 0)
- `--base-url <URL>` — explicit OpenAI‑compatible base URL (e.g., `http://localhost:1234/v1`)
- `--model <ID|substring>` - exact model id or a case-insensitive substring; ties break deterministically (alphabetical)
- `--provider <ID>` — provider key for `[model_providers.<id>]` (e.g., `lmstudio`, `ollama`, `custom`)
- `--profile <NAME>` — profile name for `[profiles.<name>]` (default deduced from provider)
- `--api-key <VAL>` — dummy key to place in an env var
- `--env-key-name <NAME>` — env var name that holds the API key (default `NULLKEY`)
- `--config-url <URL>` — preload flag defaults from a remote JSON before prompting
- `-V, --version` — print the tool version and exit

**Behavior & UX**
- `--approval-policy {untrusted,on-failure,on-request,never}` (default: `on-failure`)
- `--sandbox-mode {read-only,workspace-write,danger-full-access}` (default: `workspace-write`)
- `--network-access` — enable `sandbox_workspace_write.network_access` (omit to keep disabled)
- `--exclude-tmpdir-env-var` — exclude `$TMPDIR` from writable roots (workspace-write only; omit to include by default)
- `--exclude-slash-tmp` / `--no-exclude-slash-tmp` — exclude/include `/tmp` from writable roots (workspace-write only)
- `--writable-roots <CSV>` — extra writable roots for workspace-write (e.g., `/workspace,/data`)
- `--file-opener {vscode,vscode-insiders,windsurf,cursor,none}` (default: `vscode`)
- `--open-config` — after writing files, print the exact editor command to open `config.toml` (no auto-launch)
- `--tui-notifications` — enable desktop notifications in the TUI (omit to keep disabled)
- `--tui-notification-types <CSV>` — filter to specific types: `agent-turn-complete,approval-requested`
- `--reasoning-effort {minimal,low,medium,high}` (default: `low`)
- `--reasoning-summary {auto,concise,detailed,none}` (default: `auto`)
- `--verbosity {low,medium,high}` (default: `medium`)
- `--hide-agent-reasoning` / `--show-raw-agent-reasoning`

**History persistence & storage**
- `--no-history` - sets `history.persistence=none` (otherwise `save-all`)
- `--history-max-bytes <N>` - limit history size
- `--disable-response-storage` - do not store responses
- `--state-file <PATH>` - use a custom linker state JSON path (default `$CODEX_HOME/linker_config.json`)
- `--workspace-state` - prefer `./.codex-linker.json` in the current directory for linker state (auto-created when missing)
- `--doctor-detect-features` - while running `--doctor`, probe advanced API features (tool_choice, response_format, reasoning)

**Keychain (optional)**
- `--keychain {none,auto,macos,dpapi,secretstorage}` — when `--api-key` is provided, store it in an OS keychain:
  - `auto` → macOS Keychain on macOS, DPAPI on Windows, Secret Service on Linux
  - `macos` → macOS `security add-generic-password`
  - `dpapi` → Windows Credential Manager (Generic Credential)
  - `secretstorage` → Linux Secret Service (via optional `secretstorage` package)
  - `none` (default) → do nothing
  Notes: This is best‑effort and never required; failures are logged and ignored. Config files still use env vars — secrets are not written to TOML/JSON/YAML.

**Multiple providers & profiles**
- `--providers lmstudio,ollama` - add predefined routes for both providers and create matching profiles.
   - Also supports: `vllm`, `tgwui`, `tgi`, `openrouter` (common local ports are probed automatically).

**Dry-run diffs**
- `--dry-run --diff` - show colorized, symbol-rich diffs in TTY (falls back to unified diff when color is unavailable). Additions are green `+`, deletions red `-`, unchanged lines dim.

**Non-interactive**
- `--yes` - suppress prompts when inputs are fully specified (implies `--auto` and defaults `--model-index 0` when `--model` is not provided).
- Honors `NO_COLOR` and non‑TTY: disables ANSI; banners are omitted to keep logs clean.

### Short Flag Map (complete)
- Startup: `-a` `--auto`, `-A` `--full-auto`, `-Q` `--yes`, `-F` `--clear`, `-V` `--version`
- Selection: `-b` `--base-url`, `-m` `--model`, `-i` `--model-index`, `-P` `--provider`, `-l` `--providers`, `-p` `--profile`
- Output: `-j` `--json`, `-y` `--yaml`, `-n` `--dry-run`, `-Z` `--diff`
  - Open helper: `--open-config` (prints editor command; never auto-launches)
- Logging: `-v` `--verbose`, `--log-level/--level <debug|info|warning|error>`, `-f` `--log-file`, `-J` `--log-json`, `-R` `--log-remote`
- Secrets: `--keychain {none,auto,macos,dpapi,secretstorage,secretservice,pass,bitwarden,bw,bitwarden-cli,1password,1passwd,op}`
- Config URL / state: `-c` `--config-url`, `-x` `--state-file`
- Spec knobs: `-q` `--approval-policy`, `-s` `--sandbox-mode`, `-o` `--file-opener`, `-r` `--reasoning-effort`, `-u` `--reasoning-summary`, `-B` `--verbosity`
- History persistence/storage: `-H` `--no-history`, `-N` `--history-max-bytes`, `-d` `--disable-response-storage`
- Model limits: `-w` `--model-context-window`, `-t` `--model-max-output-tokens`, `-D` `--project-doc-max-bytes`
- Visibility/other: `-g` `--hide-agent-reasoning`, `-G` `--show-raw-agent-reasoning`, `-Y` `--model-supports-reasoning-summaries`, `-C` `--chatgpt-base-url`
- Experimental: `-U` `--experimental-resume`, `-I` `--experimental-instructions-file`, `-X` `--experimental-use-exec-command-tool`, `-O` `--responses-originator-header-internal-override`, `-M` `--preferred-auth-method`, `-W` `--tools-web-search`, `-z` `--azure-api-version`, `-K` `--request-max-retries`, `-S` `--stream-max-retries`, `-e` `--stream-idle-timeout-ms`

Note: All single-letter shorts are already used; `--log-level` offers an alias `--level` for convenience. Use `--level info` (for example) or `-v` for a quick DEBUG/WARNING toggle.

Post‑run report includes: target file path, backup path (if created), profile, provider, model, context window, and max tokens.

## Docker

Build the image locally (includes Codex CLI and this tool):
```bash
docker build -t codex-cli-linker:local .
```

Run with your `~/.codex` mounted so configs persist on the host:
```bash
docker run --rm -it \
  -e CODEX_HOME=/data/.codex \
  -v "$HOME/.codex:/data/.codex" \
  codex-cli-linker:local --auto
```

Compose option (uses `docker-compose.yml`):
```bash
docker compose up --build codex-linker
```

Notes:
- To target a local server on the host, use `--base-url http://host.docker.internal:1234/v1` on macOS/Windows. On Linux, consider `network_mode: host` in compose.
- The container never auto-launches external apps; it only prints suggested commands.
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
- `--wire-api {chat,responses}` — wire protocol for the provider
- `--http-header KEY=VAL` — static HTTP header (repeatable)
- `--env-http-header KEY=ENV_VAR` — env‑sourced header (repeatable)
- `--notify '["program","arg1",...]'` or `program,arg1,...` — top‑level `notify`
- `--instructions <TEXT>` — top‑level `instructions`
- `--trust-project <PATH>` — mark a project/worktree as trusted (repeatable)

**Output formats**
- `--json` — also write `~/.codex/config.json`
- `--yaml` — also write `~/.codex/config.yaml`
- `--dry-run` — print configs to stdout without writing files

**Diagnostics**
- `--verbose` — enable INFO/DEBUG logging
- `--log-file <PATH>` — append logs to a file
- `--log-json` — also emit logs as JSON to stdout
- `--log-remote <URL>` — POST log records to an HTTP endpoint

> The `--launch` flag is intentionally disabled; the script prints the exact `npx codex --profile <name>` command (or `codex --profile <name>` if installed) instead of auto‑launching.


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
  - `tui.style` — TUI style (e.g., `table`)
  - `tui.notifications` — boolean to enable all notifications, or array of types
  - `disable_response_storage`
  - `history.persistence` & `history.max_bytes`

- **`[model_providers.<id>]`** *(only the active one is emitted)*
  - `name` — human label (e.g., "LM Studio", "Ollama")
  - `base_url` — your selected base URL, normalized
  - `env_key` — environment variable holding the API key
  - `wire_api` — `chat` or `responses`
  - `request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`
  - `http_headers` — static headers map
  - `env_http_headers` — env‑sourced headers map
  - `query_params.api-version` *(when `--azure-api-version` is provided)*

- **`mcp_servers.<id>`**
  - `command`, `args`, `env`, optional `startup_timeout_ms` (default: 10000)

- **`sandbox_workspace_write`** (applies when `sandbox_mode = "workspace-write"`)
  - `writable_roots` — extra writable roots (cwd, $TMPDIR, and /tmp are writable by default unless excluded)
  - `network_access` — allow network in workspace-write (default: false)
  - `exclude_tmpdir_env_var` — exclude `$TMPDIR` (default: false)
  - `exclude_slash_tmp` — exclude `/tmp` (default: false)

- **`[profiles.<name>]`**
  - `model`, `model_provider`
  - `model_context_window`, `model_max_output_tokens`
  - `approval_policy`

> The tool deliberately **does not store API keys in the file**.


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


## Environment variables

- `CODEX_HOME` — overrides the config directory (default: `~/.codex`).
- `NULLKEY` — default env var this tool initializes to `"nullkey"` so configs never need to include secrets; change with `--env-key-name`.
  - Optional helper scripts:
    - macOS/Linux: `source scripts/set_env.sh`
    - Windows: `scripts\set_env.bat`

> If your provider requires a key, prefer exporting it in your shell and letting Codex read it from the environment rather than writing it to disk.


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




## Windows Defender False Positive

The single‑file binaries are built with PyInstaller, which can occasionally trigger false‑positive warnings from Windows Defender or other AV engines.

Mitigations
- Prefer the source or PyPI install: `pipx install codex-cli-linker` (or `pip install --user codex-cli-linker`) and run `codex-cli-linker`.
- Build locally from source: `python -m pip install build pyinstaller && pyinstaller -F -n codex-cli-linker codex-cli-linker.py`.
- Verify checksum against the GitHub Release artifact SHA shown in the release details.
- Optionally upload the artifact to VirusTotal to confirm multi‑engine status.

Note: We do not include third‑party code in the binary; it is produced directly from this repository’s source. If warnings persist, prefer the PyPI or source‑based install method.


## Changelog

See [changelog.md](./changelog.md) for a summary of notable changes by version.


## Development

See [development.md](./development.md) for CI, release, and code map information.

### CMake pipeline (optional)

You can use CMake to run common tasks for this Python tool (no extra Python deps required):

```bash
# Configure once
cmake -S . -B build

# Syntax check
cmake --build build --target check

# Run unit tests via CTest
cmake --build build --target test        # or: ctest --test-dir build -V

# Run the tool with flags controlled by cache vars
cmake -S . -B build \
  -DCODEX_AUTO=ON \
  -DCODEX_JSON=ON \
  -DCODEX_BASE_URL=http://localhost:1234/v1
cmake --build build --target run

# Handy aggregate target
cmake --build build --target ci          # runs check + test
```

Configurable cache variables for `run`:
- `CODEX_AUTO`, `CODEX_FULL_AUTO`, `CODEX_JSON`, `CODEX_YAML`, `CODEX_DRY_RUN`, `CODEX_VERBOSE`
- `CODEX_BASE_URL`, `CODEX_PROVIDER`, `CODEX_PROFILE`, `CODEX_MODEL`, `CODEX_MODEL_INDEX`

This keeps side effects explicit (no auto-launch) and matches the repo’s cross‑platform, no‑deps philosophy.

### Makefile helpers (optional)

GNU Make wrapper around the CMake targets:

```bash
# Configure & run checks/tests
make configure
make check
make test

# Run the tool (pass flags as variables)
make run AUTO=1 JSON=1 BASE_URL=http://localhost:1234/v1

# Aggregate
make ci

# Clean build dir
make clean
```



## License

Released under the MIT License. See [license.md](./license.md) for details.
