#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
SKIP_TESTS="${SKIP_TESTS:-0}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is required." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "Error: pip is required. In Kaggle, run: python -m pip install -q pip" >&2
  exit 1
fi

if [[ "$SKIP_INSTALL" != "1" ]]; then
  echo "Installing/updating Python dependencies into the active environment"
  "$PYTHON_BIN" -m pip install -q -r requirements.txt
fi

if [[ "$SKIP_TESTS" != "1" ]]; then
  echo "Running tests"
  "$PYTHON_BIN" -m pytest -q
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
echo "Starting RAG app at http://${HOST}:${PORT}"
exec env HOST="$HOST" PORT="$PORT" "$PYTHON_BIN" -c 'from app.web import app; import os; app.run(host=os.environ["HOST"], port=int(os.environ["PORT"]), debug=False)'
