"""Meetings cockpit read route: calendar home."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server import google_client
from server.tools import google

router = APIRouter()


@router.get("/meetings/today")
def meetings_today() -> list[dict]:
    if not google_client.is_authorized():
        raise HTTPException(503, "Google not authorized. Run: uv run python -m server.google_client auth")
    return google.calendar_list()
