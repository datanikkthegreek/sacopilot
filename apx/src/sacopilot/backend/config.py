"""Central configuration: paths, env, model. No secrets in code."""
from __future__ import annotations

import os
from pathlib import Path

# --- Endpoint ----------------------------------------------------------------
# Target the Databricks AI Gateway. Set these in the environment (the Anthropic
# SDK reads ANTHROPIC_BASE_URL + the token automatically):
#   ANTHROPIC_BASE_URL=https://adb-7405607030687545.5.azuredatabricks.net/ai-gateway/anthropic
#   ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN = a token for that workspace
# Structured outputs aren't supported on the gateway; the classifier falls back
# to a JSON-prompt path automatically.

# --- Model -------------------------------------------------------------------
# Spec model is claude-opus-4-8. Some endpoints prefix model IDs: the Databricks
# AI Gateway serves it as `databricks-claude-opus-4-8`. Auto-detect from the
# base URL, override with SACOPILOT_MODEL.
def _default_model() -> str:
    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    if "databricks" in base or "ai-gateway" in base:
        return "databricks-claude-opus-4-8"
    return "claude-opus-4-8"

MODEL = os.environ.get("SACOPILOT_MODEL", _default_model())

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

# --- Lakebase (Databricks Postgres) — classification store -------------------
# Classifications persist here (Gmail can't hold the taxonomy via the MCP). The
# Postgres password is an OAuth credential minted by the Databricks CLI.
LAKEBASE_PROFILE = os.environ.get("SACOPILOT_LAKEBASE_PROFILE", "DEFAULT")
LAKEBASE_PROJECT = os.environ.get("SACOPILOT_LAKEBASE_PROJECT", "sacopilot")
LAKEBASE_BRANCH = os.environ.get("SACOPILOT_LAKEBASE_BRANCH", "production")
LAKEBASE_ENDPOINT = os.environ.get("SACOPILOT_LAKEBASE_ENDPOINT", "primary")
LAKEBASE_DB = os.environ.get("SACOPILOT_LAKEBASE_DB", "sacopilot")

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
