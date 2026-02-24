#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -x "$BASE_DIR/venv/bin/python" ]; then
  PY="$BASE_DIR/venv/bin/python"
elif [ -x "$BASE_DIR/.venv38/bin/python" ]; then
  PY="$BASE_DIR/.venv38/bin/python"
else
  PY="python3"
fi

cd "$BASE_DIR"
"$PY" scripts/cron_auto_check.py
