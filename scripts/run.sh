#!/usr/bin/env bash
# Run the repository version of codex-cli-linker directly.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"
exec "$PY" "$REPO_DIR/codex-cli-linker.py" "$@"

