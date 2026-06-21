#!/usr/bin/env bash
# Launch SA Copilot locally: FastAPI backend (:8000) + React dev server (:5173).
set -euo pipefail
cd "$(dirname "$0")"

# Load local secrets (ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY) if present.
# .env is gitignored; never commit it.
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT

echo "→ backend  http://localhost:8000"
uv run uvicorn app:app --reload --port 8000 &

if [ -d frontend/node_modules ]; then
  echo "→ frontend http://localhost:5173"
  (cd frontend && npm run dev) &
else
  echo "frontend deps not installed (cd frontend && npm install) — backend only"
fi

wait
