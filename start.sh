#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8020}"
BIND_HOST="127.0.0.1"
if [[ "${ALLOW_LAN:-0}" =~ ^(1|true|yes)$ ]]; then
  BIND_HOST="0.0.0.0"
fi

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r backend/requirements.txt
fi

if [[ ! -f "data/data.json" ]]; then
  .venv/bin/python scripts/build_initial_data.py
fi

nohup .venv/bin/python -m uvicorn backend.app.main:app --host "$BIND_HOST" --port "$PORT" > zta-os-server.log 2> zta-os-server.err.log &
echo $! > zta-os.pid
echo "ZTA OS gestartet auf http://${BIND_HOST}:${PORT} (PID $(cat zta-os.pid))"
