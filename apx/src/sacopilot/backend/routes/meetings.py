"""Meetings cockpit route: Google calendar — work-week (Mon-Fri) view."""
from __future__ import annotations

import datetime as _dt

from fastapi import HTTPException

from sacopilot.backend import mcp_google
from sacopilot.backend.tools import google

from sacopilot.backend.core import create_router
router = create_router()


def _week_bounds(start: str | None) -> tuple[_dt.datetime, _dt.datetime, str]:
    """Monday 00:00 .. Saturday 00:00 (local) for the week containing `start`
    (YYYY-MM-DD), defaulting to the current week. Returns (min, max, monday)."""
    day = _dt.date.fromisoformat(start) if start else _dt.date.today()
    monday = day - _dt.timedelta(days=day.weekday())  # weekday(): Mon=0
    lo = _dt.datetime.combine(monday, _dt.time.min).astimezone()
    hi = lo + _dt.timedelta(days=5)  # through Friday end (Sat 00:00)
    return lo, hi, monday.isoformat()


@router.get("/meetings/week")
def meetings_week(start: str | None = None) -> dict:
    """Calendar events for the Mon-Fri work week containing `start`.

    Fetched per-day: a whole-week request is large enough to trip the MCP's
    privacy file-diversion (returns a temp-file pointer, not JSON); per-day
    responses stay small and inline."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec). Check your Databricks CLI session.")
    lo, _, monday = _week_bounds(start)
    events: list[dict] = []
    for i in range(5):
        d0 = lo + _dt.timedelta(days=i)
        d1 = d0 + _dt.timedelta(days=1)
        try:
            events += google.calendar_list(start_iso=d0.isoformat(), end_iso=d1.isoformat(), max_results=50)
        except Exception:
            pass  # skip a day that fails rather than dropping the whole week
    return {"monday": monday, "days": 5, "events": events}


@router.get("/meetings/today")
def meetings_today() -> list[dict]:
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec). Check your Databricks CLI session.")
    return google.calendar_list()
