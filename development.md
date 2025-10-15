# Development

Refer to the [README](./readme.md) for project overview, installation, and usage instructions.

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
scripts\\tag_release.ps1 v0.2.1
```

The script verifies a clean working tree, validates `vX.Y.Z` format, creates an annotated tag, and pushes it to `origin`. Publishing the GitHub Release for that tag triggers binaries + PyPI publish.

### Releases & Downloads

- Latest: https://github.com/supermarsx/codex-cli-linker/releases/latest
- All releases: https://github.com/supermarsx/codex-cli-linker/releases

<a href="https://github.com/supermarsx/codex-cli-linker/releases/latest"><img alt="Download latest" src="https://img.shields.io/badge/⬇%20Download-Latest%20Release-0b5fff?style=flat-square" /></a>
<a href="https://github.com/supermarsx/codex-cli-linker/releases"><img alt="All releases" src="https://img.shields.io/badge/Releases-All-555?style=flat-square" /></a>

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
