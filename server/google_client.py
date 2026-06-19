"""Google OAuth (installed-app flow) + cached, auto-refreshing service clients.

One OAuth covers Calendar / Drive / Docs / Gmail (see config.GOOGLE_SCOPES).
Token cached at ~/.sacopilot/google-token.json; refreshed transparently.

First-time setup (one-time, interactive):
    uv run python -m server.google_client auth
This needs an OAuth *client secret* (Desktop app) at
~/.sacopilot/google-client-secret.json (override via SACOPILOT_GOOGLE_CLIENT_SECRET).
"""
from __future__ import annotations

import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from server import config

_credentials: Credentials | None = None


def _load_credentials() -> Credentials | None:
    """Load cached creds, refreshing if expired. Returns None if not yet authed."""
    global _credentials
    if _credentials and _credentials.valid:
        return _credentials
    if config.GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(
            str(config.GOOGLE_TOKEN_PATH), config.GOOGLE_SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save(creds)
        if creds and creds.valid:
            _credentials = creds
            return creds
    return None


def _save(creds: Credentials) -> None:
    config.ensure_app_home()
    config.GOOGLE_TOKEN_PATH.write_text(creds.to_json())


def authorize() -> Credentials:
    """Run the interactive installed-app OAuth flow and cache the token."""
    if not config.GOOGLE_CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"Missing OAuth client secret at {config.GOOGLE_CLIENT_SECRET_PATH}. "
            "Create a Desktop OAuth client in Google Cloud Console, download the "
            "JSON, and save it there (or set SACOPILOT_GOOGLE_CLIENT_SECRET)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_CLIENT_SECRET_PATH), config.GOOGLE_SCOPES
    )
    creds = flow.run_local_server(port=0)
    _save(creds)
    global _credentials
    _credentials = creds
    return creds


def get_credentials() -> Credentials:
    creds = _load_credentials()
    if not creds:
        raise RuntimeError(
            "Google not authorized. Run: uv run python -m server.google_client auth"
        )
    return creds


def is_authorized() -> bool:
    return _load_credentials() is not None


# Cached service clients (built lazily, share one credential).
_services: dict[str, object] = {}


def _service(name: str, version: str):
    key = f"{name}:{version}"
    if key not in _services:
        _services[key] = build(name, version, credentials=get_credentials(), cache_discovery=False)
    return _services[key]


def gmail():
    return _service("gmail", "v1")


def calendar():
    return _service("calendar", "v3")


def drive():
    return _service("drive", "v3")


def docs():
    return _service("docs", "v1")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        authorize()
        print(f"Authorized. Token cached at {config.GOOGLE_TOKEN_PATH}")
    else:
        print("authorized" if is_authorized() else "not authorized")
