# Changelog

## v0.1.3

### Added
- Release notes for this iteration (`docs/release-notes/v0.1.3.md`) highlighting the logging shim fix and broadened QA surface.
- High-signal regression tests that exercise the doctor feature probe, asynchronous HTTP logging queue, keychain `pass` backend flows, update-check entrypoints, and prompt detector helper signatures.

### Changed
- The compatibility shim now mirrors `src` into `PYTHONPATH` before spawning subprocesses so doctor logging checks and other child processes load the in-repo modules deterministically.
- Homebrew formula and Scoop manifest now point to the v0.1.3 artifacts; Scoop URL updated pending the freshly built Windows binary hash.
- Documentation ordering in the changelog cleaned up to keep the latest version at the top for easier scanning.

### Fixed
- Remote logging subprocesses no longer crash with `ModuleNotFoundError`, restoring the doctor feature probe when `PYTEST_CURRENT_TEST` is unset.
- Update-check integration tests reuse the CLI shim module so type exports stay in sync with release packaging.

### Maintenance
- Bumped project metadata to `0.1.3`, regenerated sdist/wheel via `python -m build`, and verified formatting (`ruff`, `black`) plus the full test suite.
- Ensured release packaging artefacts (sdist, wheel) incorporate the extended tests and shim adjustments.

## v0.1.2

Highlights
- Add ARM builds for Linux and macOS in Release workflow
- Optional keychain backend via `--keychain` (macOS Keychain, Windows DPAPI, Linux Secret Service when available)
- Structured logging fields + `--log-level`/`--level`, `--log-remote` buffered async sink with drop-oldest policy
- Safer I/O: atomic writes with fsync + `os.replace`; `.bak` only when target existed
- Dry-run diffs (`--dry-run --diff`) and post-run summary (target, backup, profile, provider, model, context/max tokens)
- Extended local server probes (vLLM, Text-Gen-WebUI OpenAI plugin, TGI shim, OpenRouter local)
- Model selection accepts substrings with deterministic tie-break; `--yes` non-interactive option
- Multi-provider profiles via `--providers` (lmstudio, ollama, vllm, tgwui, tgi, openrouter, jan, llamafile, gpt4all, local)
- Windows: `clear_screen` disabled by default; `--clear` to enable
- Docs: badges with links, coverage badge, multiple Quick Starts, Dockerfile + compose, full short-flag map; `--keychain` documented
- Minimal refactor: add `cli.py`, `detect.py`, `render.py`, `io_safe.py`, `spec.py` facades

Fixes and maintenance
- Lint and format clean-up (ruff, black)
- CI guardrails and versioning remain in place

All notable changes to this project are documented here. The project follows
[Semantic Versioning](https://semver.org/) and a lightweight variant of
[Keep a Changelog](https://keepachangelog.com/).

## [0.1.1] - 2025-09-07
### Added
- GitHub Actions workflows for tagged releases: build PyInstaller binaries and publish to PyPI via Trusted Publishing.
- Contributor guidance in `agents.md`.

### Changed
- Code style cleanups (ruff + black) and test suite lint cleanup.
- Relaxed coverage gate in CI (removed `--cov-fail-under=100`), retained overall timeout.

### Fixed
- Logging reliability improvements: prevent duplicate handlers, escape JSON log messages, and ensure `HTTPHandler` import for remote logging.

## [0.1.0] - 2025-08-31
### Added
- Initial release of codex-cli-linker: single-file, no-deps tool to auto-detect local servers (LM Studio, Ollama), pick a model, and emit Codex config in TOML (optionally JSON/YAML). Includes safe backups and a small persisted state file.

