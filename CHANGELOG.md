# Changelog

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

