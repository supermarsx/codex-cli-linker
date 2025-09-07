
# Repository Guidelines

These guidelines keep contributions consistent, safe, and easy to review for the codex-cli-linker project.

## Project Structure & Modules
- `codex-cli-linker.py` — single-file tool (no third‑party deps).
- `scripts/` — small helpers (`set_env.sh`, `set_env.bat`).
- Docs: `readme.md`, `spec.md`, `license.md`, `config.toml.example`.
- Writes configs under `~/.codex/` (or `$CODEX_HOME`). Never commits user configs.

## Build, Test, and Development Commands
- Run interactively: `python3 codex-cli-linker.py`
- Auto‑detect server: `python3 codex-cli-linker.py --auto`
- Also emit JSON/YAML: `python3 codex-cli-linker.py --json --yaml`
- Quick sanity check (syntax): `python3 -m py_compile codex-cli-linker.py`
- Optional: run with a specific base URL: `python3 codex-cli-linker.py --base-url http://localhost:1234/v1`

## Coding Style & Naming Conventions
- Python 3.8+, PEP 8, 4‑space indentation, snake_case for vars/functions, UpperCamelCase for classes.
- Prefer type hints and short, single‑purpose helpers; keep the tool dependency‑free and cross‑platform.
- Match existing console UX (color helpers, concise messages, no auto‑launch side effects).
- Keep configuration shaping centralized in `build_config_dict()`; avoid duplicating schema logic.

## Testing Guidelines
- If adding tests, place them in `tests/` named `test_*.py`; use `unittest` from stdlib.
- Run tests: `python3 -m unittest -v` (from repo root).
- Manual verification: run with `--auto` against LM Studio or Ollama, or point `--base-url <.../v1>` to a compatible server and confirm files in `~/.codex/` (TOML always; JSON/YAML when requested).

## Commit & Pull Request Guidelines
- Commits: short, imperative present tense (e.g., "Update docs", "Fix model picker"). Emoji is fine but optional.
- PRs must include: purpose summary, before/after behavior, minimal repro or commands used, platform(s) tested, and linked issue(s) if applicable.
- Keep diffs surgical; avoid unrelated refactors. Preserve single‑file design unless a clear need is demonstrated.

## Security & Configuration Tips
- Do not store secrets in files. The tool uses `NULLKEY` as a harmless placeholder; prefer environment variables.
- Preserve backup behavior for config files (`*.bak`) and respect `$CODEX_HOME`.
- Never auto‑launch external apps in new features; print commands instead.

## Agent‑Specific Notes
- Follow this AGENTS.md. Maintain no‑deps policy, schema parity in TOML/JSON/YAML emitters, and consistent prompts.
- When expanding features, thread them via existing pickers and emitters; prefer minimal, reversible changes.