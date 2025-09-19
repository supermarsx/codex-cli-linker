# Homebrew Support

## Installing via Homebrew

```bash
brew tap supermarsx/codex-cli-linker https://github.com/supermarsx/codex-cli-linker
brew install supermarsx/codex-cli-linker/codex-cli-linker
codex-cli-linker --auto
```

Homebrew installs an isolated virtual environment under `$(brew --cellar)/codex-cli-linker/<version>`
that exposes the `codex-cli-linker` entry point on your PATH. The CLI now recognises
Homebrew installs and checks GitHub releases for updates by default.

To upgrade when a new release lands:

```bash
brew update
brew upgrade codex-cli-linker
```

## Maintaining the Formula

The Homebrew formula lives at `Formula/codex-cli-linker.rb` in this repository. When
publishing a new release:

1. Update `version` in `pyproject.toml` and tag the release as `v<version>`.
2. Repoint the formula `url` to the new tag tarball and update its `sha256`.
   You can obtain the checksum with:
   ```bash
   curl -L -o codex-cli-linker-<version>.tar.gz \
     https://codeload.github.com/supermarsx/codex-cli-linker/tar.gz/refs/tags/v<version>
   shasum -a 256 codex-cli-linker-<version>.tar.gz
   ```
3. Commit the formula change alongside the rest of the release automation.
4. Push the tag, then run `brew update` locally to validate the install path.

If you publish prebuilt single-file binaries, keep them in the GitHub Releases page; the
Homebrew formula intentionally installs from source to avoid arch-specific artifacts.
