"""Mail cockpit routes — served from the Lakebase inbox cache.

Sync (server/sync.py) populates the cache from Gmail; list/open then read from
Postgres (fast). "Classify new" classifies cached unclassified conversations; a
facet edit corrects one. Bodies are cached lazily on first open.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sacopilot.backend import classifier, lakebase, mcp_google, reply as _reply, sync, taxonomy
from sacopilot.backend.tools import classify as _classify
from sacopilot.backend.tools import google

from sacopilot.backend.core import create_router
router = create_router()


@router.get("/mail/taxonomy")
def mail_taxonomy() -> dict:
    """The controlled vocabulary for the facet dropdowns (avoids client drift)."""
    return {
        "type": taxonomy.TYPE, "org": taxonomy.ORG, "prio": taxonomy.PRIO,
        "dbx": taxonomy.DBX, "bosch": taxonomy.BOSCH, "bu": taxonomy.BU,
    }


@router.get("/mail/threads")
def mail_threads(limit: int = 100, offset: int = 0, unread: bool = False,
                 status: str | None = None, label: str | None = None) -> dict:
    """Inbox conversations from the cache (date-sorted, paginated). No MCP calls."""
    try:
        threads = lakebase.list_threads(
            limit=limit, offset=offset, unread=unread or None, status=status, label=label)
        counts = lakebase.count_threads()
    except Exception as e:
        raise HTTPException(503, f"Lakebase unavailable: {e}")
    return {"threads": threads, "counts": counts,
            "has_more": len(threads) == limit}


@router.get("/mail/thread/{thread_id}")
def mail_thread(thread_id: str) -> dict:
    """Full conversation for the reading pane. Cache-through: missing bodies are
    fetched once from Gmail, stored, then served from the cache thereafter."""
    try:
        msgs = lakebase.get_thread_messages(thread_id)
    except Exception as e:
        raise HTTPException(503, f"Lakebase unavailable: {e}")
    if not msgs:
        raise HTTPException(404, "thread not in cache; run sync")
    if any(m["body_html"] is None and m["body_text"] is None for m in msgs):
        if not mcp_google.is_available():
            raise HTTPException(503, "Google MCP unavailable; cannot load bodies.")
        for m in msgs:
            if m["body_html"] is None and m["body_text"] is None:
                try:
                    full = google.gmail_get_message(m["message_id"])
                    m["body_html"], m["body_text"] = full["body_html"], full["body_text"]
                    lakebase.store_body(m["message_id"], m["body_html"], m["body_text"])
                except Exception:
                    m["body_text"] = m["snippet"] or ""
    facets = None
    try:
        facets = lakebase.facets_for([thread_id]).get(thread_id)
    except Exception:
        pass
    return {"thread_id": thread_id, "messages": msgs, "facets": facets}


@router.post("/mail/sync")
async def mail_sync() -> StreamingResponse:
    """Sync the inbox into Lakebase; stream progress over SSE."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec).")

    async def event_stream():
        try:
            gen = sync.sync_inbox()
            while True:
                event = await asyncio.to_thread(lambda: next(gen, None))
                if event is None:
                    break
                yield _sse(event)
        except Exception as e:
            yield _sse({"type": "error", "message": f"{type(e).__name__}: {e}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/mail/classify")
async def mail_classify() -> StreamingResponse:
    """Classify every cached, unclassified inbox conversation; stream progress."""

    async def event_stream():
        try:
            pending = await asyncio.to_thread(classifier.unclassified_threads)
            examples = await asyncio.to_thread(classifier.few_shot_examples)
            total = len(pending)
            yield _sse({"type": "start", "total": total})
            for i, thread in enumerate(pending, 1):
                try:
                    res = await asyncio.to_thread(classifier.classify_thread, thread, examples)
                    yield _sse({"type": "progress", "done": i, "total": total,
                                "thread_id": res["thread_id"], "labels": res["labels"],
                                "facets": res["facets"], "needs_review": res["needs_review"]})
                except Exception as e:
                    yield _sse({"type": "item_error", "done": i, "total": total,
                                "thread_id": thread.get("thread_id"), "message": f"{type(e).__name__}: {e}"})
            yield _sse({"type": "done", "total": total})
        except Exception as e:
            yield _sse({"type": "error", "message": f"{type(e).__name__}: {e}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class FacetEdit(BaseModel):
    type: str
    org: str
    prio: str
    dbx: str | None = None
    bosch: str | None = None
    bu: list[str] = []


@router.put("/mail/classify/{thread_id}")
def mail_update(thread_id: str, edit: FacetEdit) -> dict:
    """Apply a manual facet correction; regenerate labels; mark adjusted."""
    facets = _classify._validate(edit.model_dump())
    facets["needs_review"] = False  # the user just reviewed it
    try:
        return lakebase.update_classification(thread_id, facets)
    except Exception as e:
        raise HTTPException(503, f"Could not update classification: {e}")


class SendIn(BaseModel):
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None
    draft_id: str | None = None


@router.post("/mail/send/{thread_id}")
def mail_send(thread_id: str, payload: SendIn) -> dict:
    """SEND a reply (irreversible). The UI gates this behind an explicit confirm.
    Sent in-thread; the lingering reply draft is deleted on success."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec).")
    try:
        google.gmail_send(to=payload.to, subject=payload.subject, body=payload.body,
                          in_reply_to_message_id=payload.reply_to_message_id)
    except Exception as e:
        raise HTTPException(502, f"Send failed: {e}")
    if payload.draft_id:
        try:
            mcp_google.call_tool("gmail_draft_delete", {"draft_id": payload.draft_id})
        except Exception:
            pass
    return {"sent": True, "to": payload.to}


@router.post("/mail/reply/{thread_id}")
def mail_reply(thread_id: str) -> dict:
    """Draft a reply (full thread + Glean + voice) and save it as a Gmail draft."""
    if not mcp_google.is_available():
        raise HTTPException(503, "Google MCP server unavailable (dbexec).")
    try:
        return _reply.draft_reply(thread_id)
    except Exception as e:
        raise HTTPException(502, f"Reply drafting failed: {e}")


class StatusEdit(BaseModel):
    status: str  # Open | In Progress | Completed


@router.put("/mail/status/{thread_id}")
def mail_status(thread_id: str, edit: StatusEdit) -> dict:
    """Set a conversation's status. Completed archives it in Gmail (remove INBOX)
    and drops it from the inbox view."""
    if edit.status not in ("Open", "In Progress", "Completed"):
        raise HTTPException(422, f"invalid status {edit.status!r}")
    archived = False
    if edit.status == "Completed":
        if mcp_google.is_available():
            try:
                google.gmail_archive_thread(thread_id)
                archived = True
            except Exception as e:
                raise HTTPException(502, f"Gmail archive failed: {e}")
    try:
        lakebase.set_status(thread_id, edit.status, leave_inbox=archived)
    except Exception as e:
        raise HTTPException(503, f"Could not set status: {e}")
    return {"thread_id": thread_id, "status": edit.status, "archived": archived}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"
