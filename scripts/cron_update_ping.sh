#!/usr/bin/env bash
set -euo pipefail

# Always use project-local paths only
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Prefer project .venv38; fall back to venv; else system python3
if [ -x "/home/ubuntu/project/titan-admin/.venv38/bin/python" ]; then
  PY="/home/ubuntu/project/titan-admin/.venv38/bin/python"
elif [ -x "/home/ubuntu/project/titan-admin/venv/bin/python" ]; then
  PY="/home/ubuntu/project/titan-admin/venv/bin/python"
else
  PY="python3"
fi

cd "$BASE_DIR"
"$PY" scripts/update_ping.py
