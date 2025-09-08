# codex-cli-linker

[![CI](https://github.com/supermarsx/codex-cli-linker/actions/workflows/ci.yml/badge.svg)](https://github.com/supermarsx/codex-cli-linker/actions/workflows/ci.yml?query=branch%3Amain)
[![PyPI](https://img.shields.io/pypi/v/codex-cli-linker)](https://pypi.org/project/codex-cli-linker/)
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
- Stores a tiny linker state (`~/.codex/linker_config.json`) to remember your last choices.
- Can preload defaults from a remote JSON via `--config-url`.
- Preview the would-be files with `--dry-run` (prints to stdout, no writes).

## Features

- Auto-detects local OpenAI-compatible servers (LM Studio, Ollama, vLLM, Text‑Gen‑WebUI OpenAI plugin, TGI shim, OpenRouter local) and normalizes base URLs.
- Interactive and non-interactive flows: `--auto`, `--full-auto`, or fully manual.
- Model discovery from `/v1/models` with a simple picker or direct `--model`/`--model-index`.
- Produces TOML by default and optional JSON/YAML mirrors to keep schema parity.
- Centralized schema shaping via a single `build_config_dict()`—no duplicated logic.
- Creates safe backups (`*.bak`) before overwriting existing configs.
- Remembers last choices in `~/.codex/linker_config.json` for faster repeat runs.
- First-class cross‑platform UX: clean colors, concise messages, no auto‑launch side effects.
- Diagnostic tooling: verbose logging, file logging, JSON logs, and remote HTTP log export.
- Tunable retry/timeout parameters for flaky networks; Azure-style `api-version` support.
- Security-aware: never writes API keys to disk; favors env vars (`NULLKEY` placeholder by default).
  - Optional: `--keychain` can store your `--api-key` in the OS keychain (macOS Keychain, Windows DPAPI/Credential Manager, or Linux Secret Service via `secretstorage` when available). The config still references the env var; secrets are never written to config files.
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
- [CI](#ci)
- [Releasing](#releasing)
  - [Conventional Commits & Versioning](#conventional-commits--versioning)
  - [Helper: Create a Tag](#helper-create-a-tag)
- [Changelog](#changelog)
- [Development & code map](#development--code-map)
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
- Windows: codex-cli-linker-windows-x64.exe
- macOS:   codex-cli-linker-macos-x64
- Linux:   codex-cli-linker-linux-x64

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

# Preload defaults from a remote JSON
python3 codex-cli-linker.py --config-url https://example.com/defaults.json --auto
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

Notes:
- The package installs the single script; there is no Python package import. Run the script by name.
- On Windows PowerShell, use `py -m pip install codex-cli-linker` then run `codex-cli-linker.py`.


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
- `--approval-policy {untrusted,on-failure}` (default: `on-failure`)
- `--sandbox-mode {read-only,workspace-write}` (default: `workspace-write`)
- `--file-opener {vscode,vscode-insiders}` (default: `vscode`)
- `--reasoning-effort {minimal,low}` (default: `low`)
- `--reasoning-summary {auto,concise}` (default: `auto`)
- `--verbosity {low,medium}` (default: `medium`)
- `--hide-agent-reasoning` / `--show-raw-agent-reasoning`

**History & storage**
- `--no-history` - sets `history.persistence=none` (otherwise `save-all`)
- `--history-max-bytes <N>` - limit history size
- `--disable-response-storage` - do not store responses
- `--state-file <PATH>` - use a custom linker state JSON path (default `$CODEX_HOME/linker_config.json`)

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
- `--dry-run --diff` - show unified diffs versus existing `config.*` files instead of writing.

**Non-interactive**
- `--yes` - suppress prompts when inputs are fully specified (implies `--auto` and defaults `--model-index 0` when `--model` is not provided).
- Honors `NO_COLOR` and non‑TTY: disables ANSI; banners are omitted to keep logs clean.

### Short Flag Map (complete)
- Startup: `-a` `--auto`, `-A` `--full-auto`, `-Q` `--yes`, `-F` `--clear`, `-V` `--version`
- Selection: `-b` `--base-url`, `-m` `--model`, `-i` `--model-index`, `-P` `--provider`, `-l` `--providers`, `-p` `--profile`
- Output: `-j` `--json`, `-y` `--yaml`, `-n` `--dry-run`, `-Z` `--diff`
- Logging: `-v` `--verbose`, `--log-level/--level <debug|info|warning|error>`, `-f` `--log-file`, `-J` `--log-json`, `-R` `--log-remote`
- Secrets: `--keychain {none,auto,macos,dpapi,secretstorage}`
- Config URL / state: `-c` `--config-url`, `-x` `--state-file`
- Spec knobs: `-q` `--approval-policy`, `-s` `--sandbox-mode`, `-o` `--file-opener`, `-r` `--reasoning-effort`, `-u` `--reasoning-summary`, `-B` `--verbosity`
- History/storage: `-H` `--no-history`, `-N` `--history-max-bytes`, `-d` `--disable-response-storage`
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
  - `disable_response_storage`
  - `history.persistence` & `history.max_bytes`

- **`[model_providers.<id>]`** *(only the active one is emitted)*
  - `name` — human label (e.g., "LM Studio", "Ollama")
  - `base_url` — your selected base URL, normalized
  - `wire_api = "chat"` — wire protocol used by Codex
  - `api_key_env_var` — environment variable holding the API key
  - `request_max_retries`, `stream_max_retries`, `stream_idle_timeout_ms`
  - `query_params.api-version` *(when `--azure-api-version` is provided)*

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


## CI

GitHub Actions run four jobs:

- **lint** — `ruff check .`
- **format** — `black --check .`
- **test** — `pytest`
- **build** — `python -m build` on Ubuntu, macOS, and Windows
- **version** — validates `pyproject.toml` SemVer and not lower than latest tag
- On PRs: **Conventional Commits** title check and a **version bump guard** (blocks version changes unless it’s a release PR)
  
Tests have a global timeout (20s) to prevent hangers.

`lint`, `format`, and `test` run in parallel and fail independently. `build` runs only after all three succeed.

Coverage reporting is generated in CI and a badge (`coverage.svg`) is committed to the repo root on successful test runs.

### Run tests locally

Install the test dependencies and run the formatter, linter, and test suite:

```
python3 -m pip install --upgrade pip
python3 -m pip install pytest pytest-cov ruff black
black .
ruff check .
pytest --cov=codex_cli_linker --cov-report=term-missing
```


## Releasing

Create a GitHub Release with a semantic tag, and automation handles the rest.

- Tag format: `vX.Y.Z` (for example, `v0.2.1`).
- On publish, two workflows run:
  - `Release Binaries` — builds PyInstaller binaries for Linux, macOS, and Windows and uploads them to the same release.
  - `Publish to PyPI` — syncs `pyproject.toml` version from the tag, commits it back to the default branch, runs lint/format/tests, builds artifacts, and publishes to PyPI.

### PyPI setup (Trusted Publishing)

- Preferred: use PyPI Trusted Publishing (OIDC); no API token is required.
  - Create the project on PyPI if it doesn’t exist.
  - In the project’s settings on PyPI, add a Trusted Publisher targeting this repository and the `publish.yml` workflow.
  - Ensure the GitHub repo has permission to request OIDC tokens (the workflow already sets `id-token: write`).
- Alternative: API token
  - Add a `PYPI_API_TOKEN` repository secret.
  - In `.github/workflows/publish.yml`, set the action with `password: ${{ secrets.PYPI_API_TOKEN }}` (and remove OIDC permissions) if you prefer token-based publishing.

### Release steps

- Draft a new GitHub Release with tag `vX.Y.Z` and publish it.
- The publish workflow updates `pyproject.toml` to `X.Y.Z` and pushes the commit to the default branch.
- Binaries for all three platforms are attached to the release.
- The package is uploaded to PyPI (skip-existing enabled).

### Conventional Commits & Versioning

- Recommended commit style: Conventional Commits (e.g., `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- Follow Semantic Versioning:
  - `MAJOR` for breaking changes,
  - `MINOR` for backwards‑compatible features,
  - `PATCH` for backwards‑compatible fixes.
- Release tags must be `vX.Y.Z` (pre‑releases like `v1.2.0-rc.1` are allowed; they publish as such to PyPI).

### Helper: Create a Tag

Use the helper script to create and push a properly formatted tag:

```
chmod +x scripts/tag_release.sh
scripts/tag_release.sh v0.2.1
# On Windows PowerShell
scripts\tag_release.ps1 v0.2.1
```

The script verifies a clean working tree, validates `vX.Y.Z` format, creates an annotated tag, and pushes it to `origin`. Publishing the GitHub Release for that tag triggers binaries + PyPI publish.

### Releases & Downloads

- Latest: https://github.com/supermarsx/codex-cli-linker/releases/latest
- All releases: https://github.com/supermarsx/codex-cli-linker/releases

<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest"><img alt="Download latest" src="https://img.shields.io/badge/⬇%20Download-Latest%20Release-0b5fff" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases"><img alt="All releases" src="https://img.shields.io/badge/Releases-All-555" /></a>

## Windows Defender False Positive

The single‑file binaries are built with PyInstaller, which can occasionally trigger false‑positive warnings from Windows Defender or other AV engines.

Mitigations
- Prefer the source or PyPI install: `pipx install codex-cli-linker` (or `pip install --user codex-cli-linker`) and run `codex-cli-linker`.
- Build locally from source: `python -m pip install build pyinstaller && pyinstaller -F -n codex-cli-linker codex-cli-linker.py`.
- Verify checksum against the GitHub Release artifact SHA shown in the release details.
- Optionally upload the artifact to VirusTotal to confirm multi‑engine status.

Note: We do not include third‑party code in the binary; it is produced directly from this repository’s source. If warnings persist, prefer the PyPI or source‑based install method.


## Changelog

See `changelog.md` for a summary of notable changes by version.


## Development & code map

- Source layout (src/)
  - src/codex_linker/impl.py — full implementation (CLI, parsing, detection, emitters, IO)
  - src/codex_linker/cli.py — CLI/UI facades importing from impl
  - src/codex_linker/detect.py — probes and model listing facades
  - src/codex_linker/render.py — TOML/JSON/YAML emitters facades
  - src/codex_linker/io_safe.py — atomic write/backup/path helpers facades
  - src/codex_linker/spec.py — provider defaults/labels
- Root compatibility
  - codex-cli-linker.py — thin shim re-exporting impl so tests and direct use continue to work
- Packaging
  - pyproject.toml — src layout configured; console entry: codex-cli-linker = codex_linker:main
- Docker
  - Uses the packaged entrypoint (codex-cli-linker); persists configs at /data/.codex (mount ~/.codex:/data/.codex)
- Tests & Coverage
  - Run: python3 -m pytest -q (repo root)
  - Coverage targets both the root shim and codex_linker package
  - CI publishes coverage.svg; run coverage xml && python -m coverage_badge -o coverage.svg -f locally if desired

