# Codex CLI Linker — Functional & Technical Specification

**Repo:** `codex-cli-linker`  
**Primary entrypoint:** `codex-cli-linker.py` (single-file, no third‑party deps)  
**License:** MIT  
**Purpose:** Generate Codex CLI configuration (primarily `config.toml`, with optional `config.json`/`config.yaml`) that points Codex CLI at a local OpenAI‑compatible server (LM Studio or Ollama) or a custom base URL. It detects servers, lists models via `/v1/models`, helps users pick a model, writes config files safely (with `.bak` backup), and remembers last choices.

---

## 1) Goals & Non‑Goals

### Goals
- Detect a local OpenAI‑compatible server and its models:
  - LM Studio at `http://localhost:1234/v1`
  - Ollama at `http://localhost:11434/v1`
  - Or arbitrary custom base URL
- Interactively select a model from `/v1/models` or accept `--model` (non‑interactive).
- Emit **Codex CLI config** using modern `config.toml` structure with:
  - `model`, `model_provider`, approval/sandbox/file opener knobs, history, tools toggles
  - A provider entry under `[model_providers.<id>]` with network tuning knobs
  - A profile under `[profiles.<name>]` pinning provider + model
- Optionally emit `config.json` and `config.yaml` siblings
- Back up existing config files before writing
- Persist lightweight linker state (no secrets) to `~/.codex/linker_config.json`
- Merge remote default values via `--config-url` before prompting
- Offer helpful, colorized, cross‑platform UX

### Non‑Goals
- Managing or storing real API secrets (uses a **dummy** env key by design)
- Full lifecycle management of Codex CLI; only attempts install if missing
- Remote server lifecycle; only probes HTTP endpoints

---

## 2) User Personas & Stories

- **Local LLM tinkerer:** Runs LM Studio or Ollama locally; wants Codex CLI to target it with minimal setup.
- **DevOps/Platform engineer:** Needs a repeatable, scriptable way to produce `config.toml` consistent with Codex config spec.
- **New user:** Wants interactive prompts to choose base URL, model, and sane defaults.

**Stories**
1. As a user, I can run `python codex-cli-linker.py --full-auto` to configure using the first available model with no prompts.
2. As a user, I can run `python codex-cli-linker.py --auto` to detect LM Studio/Ollama and generate `~/.codex/config.toml`.
3. As a user, I can run with `--base-url http://host:port/v1 --model <id>` to skip prompts and produce config directly.
4. As a user, I can opt into JSON/YAML mirrors via `--json` and/or `--yaml`.
5. As a user, my previous choices are remembered across runs.

---

## 3) High‑Level Flow

```
start → load saved linker state → (auto?) detect base URL → fetch /models →
interactive pick (unless --model provided)
→ compute config dict → backup existing config → write TOML (+optional JSON/YAML) →
save linker state → show next‑step hints
```

**Server detection**
- Probes `http://localhost:1234/v1` (LM Studio) and `http://localhost:11434/v1` (Ollama) concurrently; first responder wins.
- Success when `/models` returns JSON with a `data` list.

**Model listing**
- Calls `GET {base_url}/models` with short timeout; extracts `data[*].id`.

**Context window heuristic**
- Optionally infers context window tokens from common metadata fields in the `/models` payload (e.g., `context_length`, `max_context_length`, `context_window`, `max_context_window`, `n_ctx`). Falls back to `0` if unknown.

---

## 4) CLI Interface (Arguments)

> All flags are provided by `argparse` in `codex-cli-linker.py`.

### General
- `--verbose` — enable INFO/DEBUG logging output
- `--config-url <URL>` — preload defaults from a JSON config before prompts

### Base selection & model
- `--auto` — auto‑detect base URL and skip base‑URL prompt
- `--full-auto` — imply `--auto` and pick the first available model with no prompts
- `--base-url <URL>` — override base URL (e.g., `http://localhost:1234/v1`)
- `--model <id>` — skip model picker (use the given id)
- `--model-index <int>` — when auto-selecting, choose model by list index (default 0)
- `--provider <id>` — provider id for `[model_providers.<id>]` (default inferred: `lmstudio`/`ollama`/`custom`)
- `--profile <name>` — profile name (default deduced from provider)
- `--api-key <val>` — dummy key to place in env var (local servers typically ignore)

### Core config knobs (Codex config spec)
- `--approval-policy` — default `on-failure` (allowed: `untrusted`, `on-failure`)
- `--sandbox-mode` — default `workspace-write` (allowed: `read-only`, `workspace-write`)
- `--file-opener` — default `vscode` (allowed: `vscode`, `vscode-insiders`)
- `--reasoning-effort` — default `low` (allowed: `minimal`, `low`; others clamped)
- `--reasoning-summary` — default `auto` (allowed: `auto`, `concise`)
- `--verbosity` — default `medium` (allowed: `low`, `medium`)

### History / tools / misc
- `--disable-response-storage` — sets `disable_response_storage=true`
- `--no-history` — sets `history.persistence=none` (otherwise `save-all`)
- `--history-max-bytes <int>` — maximum stored history bytes
- `--tools-web-search` — sets `tools.web_search=true`
- `--project-doc-max-bytes <int>` — default `1048576`
- `--tui <style>` — default `table` (not emitted in TOML; internal toggle)
- `--hide-agent-reasoning` / `--show-raw-agent-reasoning` — mutually exclusive toggles
- `--model-supports-reasoning-summaries` — boolean root flag
- `--chatgpt-base-url <url>` — optional root field passthrough
- `--experimental-resume`, `--experimental-instructions-file`, `--experimental-use-exec-command-tool` — passthroughs
- `--responses-originator-header-internal-override <str>` — passthrough
- `--preferred-auth-method chatgpt|apikey` — default `apikey`

### Provider network knobs
- `--request-max-retries <int>` — default `4`
- `--stream-max-retries <int>` — default `10`
- `--stream-idle-timeout-ms <int>` — default `300000`
- `--azure-api-version <str>` — if present, emits `query_params.api-version`

### Numeric model knobs
- `--model-context-window <int>` — default `0`
- `--model-max-output-tokens <int>` — default `0`

### Output toggles
- `--json` — also write `~/.codex/config.json`
- `--yaml` — also write `~/.codex/config.yaml`
- `--dry-run` — print configs to stdout without writing or backing up files

> A `--launch` flag exists but is a no‑op by design (manual Codex launch is recommended). The script can inform how to run: `npx codex --profile <name>` or `codex --profile <name>`. A helper `launch_codex(profile)` is available for cross‑platform execution (cmd, PowerShell, POSIX shells) and returns the CLI's exit code while logging the command.

---

## 5) Files, Paths & Persistence

- **CODEX_HOME**: `~/.codex` unless overridden by env `CODEX_HOME`.
- **Config outputs**
  - `~/.codex/config.toml` (always written unless `--dry-run`)
  - `~/.codex/config.json` (optional)
  - `~/.codex/config.yaml` (optional)
- **Backups**: When rewriting, existing files are moved to `<name>.<ext>.<YYYYMMDD-HHMM>.bak` allowing multiple versions to accumulate.
- **Linker state**: `~/.codex/linker_config.json` (stores base URL, provider id, profile name, model id; **no secrets**).
- **Helper scripts**: `scripts/set_env.sh` and `scripts/set_env.bat` — set `NULLKEY` env var.

---

## 6) Config Schema (emitted)

> The in‑memory config is assembled by `build_config_dict(state, args)` then rendered via purpose‑built emitters: `to_toml`, `to_json`, and `to_yaml` (all no‑deps).

### Root keys (representative)
- `model: string` — chosen model id (defaults to `gpt-5` if not selected)
- `model_provider: string` — provider id used in `model_providers`
- `approval_policy: "untrusted"|"on-failure"`
- `sandbox_mode: "read-only"|"workspace-write"`
- `file_opener: "vscode"|"vscode-insiders"`
- `sandbox_workspace_write: { writable_roots: string[], network_access: bool, exclude_tmpdir_env_var: bool, exclude_slash_tmp: bool }`
- `model_reasoning_effort: "minimal"|"low"`
- `model_reasoning_summary: "auto"|"concise"`
- `model_verbosity: "low"|"medium"`
- `profile: string`
- `model_context_window: int` (0 if unknown)
- `model_max_output_tokens: int`
- `project_doc_max_bytes: int`
- `hide_agent_reasoning: bool`
- `show_raw_agent_reasoning: bool`
- `model_supports_reasoning_summaries: bool`
- `chatgpt_base_url: string`
- `experimental_resume: string`
- `experimental_instructions_file: string`
- `experimental_use_exec_command_tool: bool`
- `responses_originator_header_internal_override: string`
- `preferred_auth_method: "chatgpt"|"apikey"`
- `tools: { web_search: bool }`
- `disable_response_storage: bool`
- `history: { persistence: "save-all"|"none", max_bytes: int }`

### Model providers (one minimal provider is emitted)
```toml
[model_providers.<provider_id>]
name = "LM Studio" | "Ollama" | <Capitalized custom>
base_url = "http://localhost:1234/v1"  # or custom
wire_api = "chat"
request_max_retries = 4
stream_max_retries = 10
stream_idle_timeout_ms = 300000
# optional when --azure-api-version is supplied
# [model_providers.<provider_id>.query_params]
#   "api-version" = "2024-xx-xx"
```

### Profiles (one active profile emitted)
```toml
[profiles.<profile_name>]
model = "<model-id>"
model_provider = "<provider_id>"
model_context_window = 0
model_max_output_tokens = 0
approval_policy = "on-failure"
```

### Example TOML output
```toml
# Generated by codex-cli-linker
model = "qwen2.5-coder"
model_provider = "lmstudio"
approval_policy = "on-failure"
sandbox_mode = "workspace-write"
file_opener = "vscode"
model_reasoning_effort = "low"
model_reasoning_summary = "auto"
model_verbosity = "medium"
profile = "lmstudio"
model_context_window = 32000
model_max_output_tokens = 0
project_doc_max_bytes = 1048576
hide_agent_reasoning = false
show_raw_agent_reasoning = true
model_supports_reasoning_summaries = false
chatgpt_base_url = ""
experimental_resume = ""
experimental_instructions_file = ""
experimental_use_exec_command_tool = false
responses_originator_header_internal_override = ""
preferred_auth_method = "apikey"
[tasks]
# (if present via future extensions)

[sandbox_workspace_write]
writable_roots = []
network_access = false
exclude_tmpdir_env_var = false
exclude_slash_tmp = false

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
model = "qwen2.5-coder"
model_provider = "lmstudio"
model_context_window = 32000
model_max_output_tokens = 0
approval_policy = "on-failure"
```

(Actual keys emitted are filtered: empty strings / empty tables are omitted; booleans and zeroes are retained.)

---

## 7) UX & Interaction Details

- Colorized output with symbols (`✓`, `ℹ`, `!`, `✗`) when terminal supports color.
- Numbered pick‑lists for base URL choice and model selection.
- Graceful clamping of out‑of‑spec choices (e.g., `--reasoning-effort medium` → `low`).
- Friendly post‑run summary with explicit `npx codex --profile …` (or `codex --profile …`) hints.

---

## 8) Security & Privacy Considerations

- **No secrets persisted:**
  - Linker state (`linker_config.json`) stores only non‑sensitive selections.
  - Default env var name for API key is `NULLKEY`; helper scripts set it to `"nullkey"`.
  - Do **not** prompt for or store real API keys; local servers typically ignore keys.
- **Backups:** Single `.bak` rotation on config files to avoid accidental loss.
- **Network:**
  - Short HTTP timeouts (default ~3s) to avoid hanging on dead endpoints.
  - No certificate pinning; intended for **local** servers (`http://localhost`).
- **Sandbox settings:**
  - `sandbox_workspace_write` defaults are conservative (no network access, empty roots). Users must opt‑in.
- **User trust/approval:**
  - `approval_policy` defaults to `on-failure` per safer execution.
- **Cross‑platform scripts:**
  - `set_env.sh` / `set_env.bat` demonstrate **testing** env setup with a dummy key only.

**Hardening guidance (future):**
- Consider refusing non‑localhost `http` endpoints unless `--allow-remote-http` is explicitly set.
- Optionally support `https` verification knobs for remote servers.
- Add checksum or signature to detect tampered `config.toml` on overwrite.

---

## 9) Error Handling & Edge Cases

- **/models unreachable:** Raise a clear error with the failing URL and reason.
- **No models returned:** Show empty list error and prompt to check server.
- **Azure variant:** If `--azure-api-version` provided, emit `query_params.api-version` under the provider.
- **Clamping:** Unknown reasoning verbosity/effort values are clamped to nearest supported.
- **History toggles:** `--no-history` flips `history.persistence` to `none`.
- **Backup failure:** Non‑fatal (warn) and proceed to overwrite (as implemented);
  if file move fails, show the exception.

---

## 10) Architecture & Key Components

- **Single module:** `codex-cli-linker.py`
  - **Color/UX helpers:** `supports_color`, `c`, `banner`, `info`, `ok`, `warn`, `err`
  - **HTTP:** `http_get_json(url, timeout)`
  - **Detection:** `detect_base_url(candidates)`
  - **Models:** `list_models(base_url)`, `try_auto_context_window(base_url, model_id)`
  - **State:** `LinkerState` dataclass with `save`/`load` to `~/.codex/linker_config.json`
  - **Config:** `build_config_dict(state, args)` → dict; `to_toml`, `to_json`, `to_yaml` emitters
  - **I/O:** `backup(path)`; writing to `CONFIG_TOML|JSON|YAML`
  - **Codex CLI detection:** `find_codex_cmd()`, `ensure_codex_cli()`, `launch_codex(profile)` for cross‑platform launching (cmd, PowerShell, POSIX shells) with exit codes and logs
  - **Interaction:** `prompt_choice`, `prompt_yes_no`, `pick_base_url`, `pick_model_interactive`
  - **Entrypoint:** `main()` with `argparse` → flow orchestration

**Dependencies:** Standard library only (e.g., `argparse`, `json`, `re`, `urllib.request`, `pathlib`, `subprocess`, `shutil`).

**OS Targets:** macOS, Linux, Windows (color detection + `.bat`/`.sh` helpers).

---

## 11) Build, Install & Run

### Requirements
- Python 3.8+
- Codex CLI (`@openai/codex-cli`) available on PATH or installable via `npm -g`.

### Installation
- Clone the repo; the tool is a single script — no pip install needed.
- (Optional) Make executable: `chmod +x codex-cli-linker.py`.
- (Optional) Global availability: place on PATH (e.g., `/usr/local/bin/`).

### Running
```bash
# Quick auto‑detect & write TOML
python codex-cli-linker.py --auto

# Custom base URL & model, emit JSON and YAML too
python codex-cli-linker.py \
  --base-url http://localhost:11434/v1 \
  --model llama3.1:8b-instruct \
  --provider ollama \
  --profile ollama \
  --json --yaml
```

---

## 12) Testing Strategy

### Unit Tests (pure functions)
- **Emitters**: Verify `to_toml`/`to_json`/`to_yaml` produce stable output for representative configs; ensure omission of empty values and retention of booleans/zeros; confirm ordering for determinism.
- **Backup**: Simulate existing files; ensure `.bak` is created/overwritten.
- **State**: `LinkerState.save/load` round‑trips.
- **Clamping**: Reasoning effort/verbosity clamping behavior.

### Integration Tests
- **HTTP contract**: Start a local HTTP test server that serves `/models` with various payloads (normal, empty, malformed), verify list & detection.
- **Context window inference**: Feed different metadata shapes and ensure correct extraction/fallback to 0.
- **End‑to‑end write**: Generate files in a temp `CODEX_HOME`, verify content + single‑slot backup behavior.

### Cross‑Platform Smoke
- Windows (PowerShell + `cmd`) & `.bat` helper; macOS/Linux with `.sh` helper; UTF‑8 output and color support checks.

### Manual Acceptance
- With LM Studio running at `:1234`, run `--auto` and pick a model; inspect generated TOML; run `npx codex --profile <name>` (or `codex --profile <name>`).
- With Ollama at `:11434`, repeat with an Ollama model id.

---

## 13) Telemetry & Logging

- No telemetry. Console logging only.
- Symbols and colors are used; fallback to plain text when color unsupported.

---

## 14) Risks & Mitigations

- **Local server variations**: `/models` may vary across vendors; emitter and model parsing written defensively and tolerate absent fields.
- **User confusion about API keys**: Provide explicit messaging that local servers usually ignore keys and that the script does **not** store secrets.
- **Overwriting configs**: Single backup to prevent data loss; `--dry-run` previews without touching files.
- **Non‑localhost servers**: Currently allowed; advise caution and consider `https` controls for remote endpoints (future work).

---

## 15) Roadmap (Future Enhancements)

- Add `--allow-remote-http` gate and `--require-https` for non‑localhost URLs.
- Optional multi‑provider emission (write multiple `[model_providers.*]` entries and multiple named profiles in one run).
- Model filtering/search in interactive picker (by substring, family, parameter count if available).
- Rich TUI mode for list selection; progress spinners for network calls.
- Pluggable discovery for additional local servers.

---

## 16) Acceptance Criteria

- Running `--auto` against a running LM Studio or Ollama produces a valid `~/.codex/config.toml` containing:
  - Correct `model` and `model_provider`
  - One provider entry with `base_url` and network knobs
  - One profile matching the chosen provider and model
  - Root fields aligned with chosen flags and with empties omitted
- If existing config exists, a `.bak` appears alongside the new file.
- `--json` and/or `--yaml` produce valid, parseable siblings.
- Linker state is created/updated and contains no secrets.

---

## 17) Repo Layout (as of this spec)

```
codex-cli-linker.py           # main tool
config.toml.example           # (placeholder)
readme.md                    # short project description
license.md                   # MIT
scripts/
  set_env.sh                 # export NULLKEY="nullkey"
  set_env.bat                # set NULLKEY=nullkey
```

---

## 18) Example: Minimal JSON/YAML mirrors

```json
{
  "model": "qwen2.5-coder",
  "model_provider": "lmstudio",
  "approval_policy": "on-failure",
  "sandbox_mode": "workspace-write",
  "file_opener": "vscode",
  "history": {"persistence": "save-all", "max_bytes": 0},
  "model_providers": {
    "lmstudio": {
      "name": "LM Studio",
      "base_url": "http://localhost:1234/v1",
      "wire_api": "chat",
      "request_max_retries": 4,
      "stream_max_retries": 10,
      "stream_idle_timeout_ms": 300000
    }
  },
  "profiles": {
    "lmstudio": {
      "model": "qwen2.5-coder",
      "model_provider": "lmstudio",
      "model_context_window": 32000,
      "model_max_output_tokens": 0,
      "approval_policy": "on-failure"
    }
  }
}
```

```yaml
model: qwen2.5-coder
model_provider: lmstudio
approval_policy: on-failure
sandbox_mode: workspace-write
file_opener: vscode
history:
  persistence: save-all
  max_bytes: 0
model_providers:
  lmstudio:
    name: "LM Studio"
    base_url: "http://localhost:1234/v1"
    wire_api: "chat"
    request_max_retries: 4
    stream_max_retries: 10
    stream_idle_timeout_ms: 300000
profiles:
  lmstudio:
    model: qwen2.5-coder
    model_provider: lmstudio
    model_context_window: 32000
    model_max_output_tokens: 0
    approval_policy: on-failure
```

---

## 19) Definition of Done

- Spec‑compliant TOML written with correct semantics and defensive omission of empties.
- Backups created; errors and warnings surfaced clearly.
- JSON/YAML mirror generation guarded by flags.
- Interactive and non‑interactive flows both covered by automated tests.
- Works on macOS, Linux, Windows without additional dependencies.

---

## 20) Continuous Integration

GitHub Actions runs five jobs:

- **lint** — `ruff check .`
- **format** — `black --check .`
- **test** — `pytest`
- **build** — `python -m build` on Ubuntu, macOS, and Windows
- **publish** — uploads build artifacts to PyPI

`lint`, `format`, and `test` execute in parallel and fail independently. `build` runs only after those three succeed, and `publish` depends on the successful completion of `build`.

