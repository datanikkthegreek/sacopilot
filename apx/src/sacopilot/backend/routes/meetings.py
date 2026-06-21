"""Meetings cockpit route: Google calendar — work-week (Mon-Fri) view +
auto-categorisation (write category colours back to Google)."""
from __future__ import annotations

import asyncio
import datetime as _dt
import json

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from sacopilot.backend import mcp_google, meeting_categorize as mc
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


def _week_events(lo: _dt.datetime) -> list[dict]:
    """Per-day fetch (whole-week requests trip the MCP privacy file-diversion)."""
    events: list[dict] = []
    for i in range(5):
        d0 = lo + _dt.timedelta(days=i)
        try:
            events += google.calendar_list(start_iso=d0.isoformat(),
                                            end_iso=(d0 + _dt.timedelta(days=1)).isoformat(),
                                            max_results=50)
        except Exception:
            pass  # skip a day that fails rather than dropping the whole week
    return events


@router.get("/meetings/week")
def meetings_week(start: str | None = None) -> dict:
    """Calendar events for the Mon-Fri work week containing `start`."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec). Check your Databricks CLI session.")
    lo, _, monday = _week_bounds(start)
    return {"monday": monday, "days": 5, "events": _week_events(lo)}


@router.post("/meetings/categorize")
async def meetings_categorize(start: str | None = None) -> StreamingResponse:
    """Auto-categorise UNCOLOURED events in the week and write the colour back to
    Google. Already-coloured events are untouched (and used as few-shot examples)."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec).")

    async def event_stream():
        try:
            lo, _, _ = _week_bounds(start)
            events = await asyncio.to_thread(_week_events, lo)
            uncoloured = [e for e in events if not e.get("color_id")]
            examples = [{**e, "category": mc.COLOR_TO_CAT[e["color_id"]]}
                        for e in events if e.get("color_id") in mc.COLOR_TO_CAT]
            if not uncoloured:
                yield _sse({"type": "done", "total": 0}); return
            mapping = await asyncio.to_thread(mc.classify, uncoloured, examples)
            total = len(mapping)
            yield _sse({"type": "start", "total": total})
            done = 0
            for e in uncoloured:
                cat = mapping.get(e["id"])
                if not cat:
                    continue
                done += 1
                try:
                    await asyncio.to_thread(google.calendar_set_color, e["id"], mc.CAT_TO_COLOR[cat])
                    yield _sse({"type": "progress", "done": done, "total": total,
                                "event_id": e["id"], "summary": e.get("summary"), "category": cat})
                except Exception as ex:
                    yield _sse({"type": "item_error", "done": done, "total": total,
                                "event_id": e["id"], "message": f"{type(ex).__name__}: {ex}"})
            yield _sse({"type": "done", "total": total})
        except Exception as ex:
            yield _sse({"type": "error", "message": f"{type(ex).__name__}: {ex}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/meetings/today")
def meetings_today() -> list[dict]:
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec). Check your Databricks CLI session.")
    return google.calendar_list()


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
