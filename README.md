# SA Copilot

Personal Solutions Architect copilot — **email triage** (auto-classify → Gmail labels,
6-facet filtering) + **meeting capture/drafting** in your voice. Local web app:
Python/FastAPI backend hosting a Claude agent loop, React cockpit frontend.

See `docs/specs/` for the design + implementation plan.

## Setup

### 1. Backend (Python, uv)
```bash
uv sync
```

Endpoint (Databricks AI Gateway) — set in your environment:
```bash
export ANTHROPIC_BASE_URL=https://adb-7405607030687545.5.azuredatabricks.net/ai-gateway/anthropic
export ANTHROPIC_API_KEY=...   # token for that workspace
```
The model auto-resolves to `databricks-claude-opus-4-8` on the gateway
(override with `SACOPILOT_MODEL`).

### 2. Google OAuth (one-time, interactive)
1. Create a **Desktop** OAuth client in Google Cloud Console; download the JSON.
2. Save it to `~/.sacopilot/google-client-secret.json`.
3. Authorize (opens a browser):
   ```bash
   uv run python -m server.google_client auth
   ```

### 3. Frontend (React, Vite)
```bash
cd frontend && npm install   # needs npm registry access
```

## Run
```bash
./dev.sh        # backend :8000 + frontend :5173
```
Open http://localhost:5173.

## Test
```bash
uv run pytest                 # classifier regression (needs ANTHROPIC creds)
```

## Notes
- **Drafts only** — the app never sends email.
- **Gmail is the source of truth** for labels; the app writes them back live.
- **Review before write** — label writes, drafts, and vault commits pause for approval.
- The Obsidian vault is **read-only** context from Mail; only the Meetings view writes
  to it (via approved `commit_writes`).
