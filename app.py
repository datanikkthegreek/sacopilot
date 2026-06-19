"""SA Copilot — FastAPI entry point.

Serves the API + SSE for the React cockpit. Run locally:
    uv run uvicorn app:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server import config

app = FastAPI(title="SA Copilot")

# Local dev: React dev server (5173) calls the API (8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness + config sanity for the frontend to show setup state."""
    return {
        "status": "ok",
        "model": config.MODEL,
        "anthropic_key": config.has_anthropic_key(),
        "google_authed": config.GOOGLE_TOKEN_PATH.exists(),
        "vault_found": config.VAULT_ROOT.exists(),
        "voice_profile_found": config.VOICE_PROFILE_PATH.exists(),
    }


from server.routes import agent as agent_routes  # noqa: E402

app.include_router(agent_routes.router, prefix="/api")
