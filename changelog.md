# Changelog

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
