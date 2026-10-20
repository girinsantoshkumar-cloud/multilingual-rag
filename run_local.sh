#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
SKIP_TESTS="${SKIP_TESTS:-0}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is required. Install Python 3.10+ and python3-venv." >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
  echo "Error: Python venv support is missing. On Debian/Ubuntu run: sudo apt-get install python3-venv" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PY="$ROOT_DIR/$VENV_DIR/bin/python"
PIP="$ROOT_DIR/$VENV_DIR/bin/pip"

echo "Installing/updating Python dependencies"
"$PY" -m pip install --upgrade pip setuptools wheel
"$PIP" install -r requirements.txt

if [[ "$SKIP_TESTS" != "1" ]]; then
  echo "Running tests"
  "$PY" -m pytest -q
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
echo "Starting RAG app at http://${HOST}:${PORT}"
exec env HOST="$HOST" PORT="$PORT" "$PY" -c 'from app.web import app; import os; app.run(host=os.environ["HOST"], port=int(os.environ["PORT"]), debug=False)'
