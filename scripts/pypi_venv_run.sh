#!/usr/bin/env bash
# Bootstrap a local venv, install codex-cli-linker from PyPI, then run it.
# Uses $CODEX_HOME/venv by default to keep the environment isolated.

set -euo pipefail

BASE_DIR="${CODEX_HOME:-$HOME/.codex}"
VENV_DIR="$BASE_DIR/venv/codex-cli-linker"

PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python is required but not found" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  mkdir -p "$(dirname "$VENV_DIR")"
  "$PY" -m venv "$VENV_DIR"
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  python -m pip -q install --upgrade pip >/dev/null 2>&1 || true
  python -m pip install -q -U codex-cli-linker
  exec "$VENV_DIR/bin/codex-cli-linker" "$@"
else
  echo "Could not activate venv at $VENV_DIR" >&2
  exit 1
fi

