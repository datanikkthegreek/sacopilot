"""Inbox → Lakebase sync (the performance foundation).

Populates the `threads` cache (metadata + date + unread) and per-message
metadata so the cockpit serves list/open from Postgres instead of hitting the
Gmail MCP live. First sync covers the whole inbox (one call per new thread);
later syncs only fetch genuinely new threads.

Bodies are NOT fetched here — they're cached lazily on first open
(routes/mail.py cache-through), keeping sync to one fetch per new thread.
"""
from __future__ import annotations

from typing import Any, Iterator

from sacopilot.backend import lakebase
from sacopilot.backend.tools import google as _google


def _q(before: int | None) -> str:
    return f"in:inbox before:{before}" if before else "in:inbox"


def _enumerate_inbox(cap: int = 1000) -> list[dict]:
    """All inbox threads (newest-first), paged past the ~100/call MCP cap by
    date window. Returns thread_list items (id/subject/from/snippet/count)."""
    out: list[dict] = []
    seen: set[str] = set()
    before: int | None = None
    while len(out) < cap:
        page = _google.gmail_thread_list(_q(before), max_results=100)
        if not page:
            break
        for t in page:
            if t["thread_id"] not in seen:
                seen.add(t["thread_id"])
                out.append(t)
        if len(page) < 100:
            break
        before = _google.thread_latest_epoch(page[-1]["thread_id"])
        if not before:
            break
    return out


def _msg_row(m: dict, ordinal: int) -> dict:
    return {
        "message_id": m["id"],
        "ordinal": ordinal,
        "from_addr": m.get("from"),
        "to_addr": m.get("to"),
        "date_str": m.get("date"),
        "internal_date": int(m["internal_date"]) if m.get("internal_date") else None,
        "subject": m.get("subject"),
        "snippet": m.get("snippet", ""),
    }


def sync_inbox(cap: int = 1000) -> Iterator[dict[str, Any]]:
    """Sync the inbox into Lakebase, yielding SSE-friendly progress events."""
    yield {"type": "phase", "phase": "enumerate"}
    threads = _enumerate_inbox(cap)
    inbox_ids = [t["thread_id"] for t in threads]
    archived = lakebase.reconcile_inbox(inbox_ids)
    have = lakebase.existing_thread_ids(inbox_ids)
    new = [t for t in threads if t["thread_id"] not in have]
    total = len(new)
    yield {"type": "start", "total": total, "inbox": len(inbox_ids), "archived": archived}

    for i, t in enumerate(new, 1):
        tid = t["thread_id"]
        try:
            detail = _google.gmail_get_thread(tid)
            msgs = detail.get("messages", [])
            unread = any("UNREAD" in (m.get("label_ids") or []) for m in msgs)
            last_ms = detail.get("latest_internal_date")
            lakebase.upsert_thread({
                "thread_id": tid,
                "subject": t.get("subject"),
                "sender": (msgs[-1].get("from") if msgs else t.get("from")),
                "snippet": t.get("snippet", ""),
                "message_count": t.get("message_count") or len(msgs) or 1,
                "last_internal_date": int(last_ms) if last_ms else None,
                "unread": unread,
            })
            lakebase.upsert_messages(tid, [_msg_row(m, o) for o, m in enumerate(msgs)])
            yield {"type": "progress", "done": i, "total": total, "thread_id": tid}
        except Exception as e:  # one bad thread shouldn't abort the sync
            yield {"type": "item_error", "done": i, "total": total,
                   "thread_id": tid, "message": f"{type(e).__name__}: {e}"}

    # Bulk unread refresh covers previously-cached threads too (cheap).
    try:
        unread = _google.gmail_thread_list("in:inbox is:unread", max_results=100)
        lakebase.set_unread([u["thread_id"] for u in unread])
    except Exception:
        pass

    yield {"type": "done", "total": total, "inbox": len(inbox_ids), "archived": archived}
