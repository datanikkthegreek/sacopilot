"""Central configuration: paths, env, model. No secrets in code."""
from __future__ import annotations

import os
from pathlib import Path

# --- Model -------------------------------------------------------------------
MODEL = "claude-opus-4-8"  # adaptive thinking, streaming (see server/agent.py)

# --- Anthropic ---------------------------------------------------------------
# Key resolved from the environment by the Anthropic SDK (ANTHROPIC_API_KEY or
# an `ant auth login` profile). Never hardcode it.
def has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

# --- Local app state ---------------------------------------------------------
APP_HOME = Path(os.environ.get("SACOPILOT_HOME", "~/.sacopilot")).expanduser()
GOOGLE_TOKEN_PATH = APP_HOME / "google-token.json"
GOOGLE_CLIENT_SECRET_PATH = Path(
    os.environ.get("SACOPILOT_GOOGLE_CLIENT_SECRET", APP_HOME / "google-client-secret.json")
).expanduser()
EMAIL_STATE_PATH = APP_HOME / "email-state.json"
CORRECTIONS_PATH = APP_HOME / "corrections.json"

# --- Obsidian vault (read-only context; reused .sync scripts) ----------------
VAULT_REPO = Path(os.environ.get("SACOPILOT_VAULT_REPO", "~/Repos/obsidian")).expanduser()
VAULT_ROOT = VAULT_REPO / "NikkTheGreek"
SYNC_DIR = VAULT_REPO / ".sync"
MOC_PATH = VAULT_ROOT / "_MOC.md"

# --- Voice profile -----------------------------------------------------------
VOICE_PROFILE_PATH = Path(
    os.environ.get("SACOPILOT_VOICE_PROFILE", "~/.vibe/voice_profile.yaml")
).expanduser()

# --- Google OAuth scopes -----------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/gmail.modify",  # read + apply labels + create drafts (never send)
]

# --- Classification ----------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.65  # below this -> add Needs/Review


def ensure_app_home() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)
