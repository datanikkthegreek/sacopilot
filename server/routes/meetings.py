"""Meetings cockpit read route: calendar home."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server import mcp_google
from server.tools import google

router = APIRouter()


@router.get("/meetings/today")
def meetings_today() -> list[dict]:
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec). Check your Databricks CLI session.")
    return google.calendar_list()
