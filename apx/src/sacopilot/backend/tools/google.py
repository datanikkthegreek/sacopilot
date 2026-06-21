"""Google read tools (Calendar / Gmail / Drive / Docs) over the MCP server.

Same function signatures the rest of the app already uses; implementations now
call the already-authenticated dbexec Google MCP server (server/mcp_google.py)
instead of a direct OAuth client. No app-side GCP/OAuth setup required.
"""
from __future__ import annotations

import base64
import datetime as _dt
import html as _html
import re
import tempfile
from pathlib import Path
from typing import Any

from sacopilot.backend import mcp_google


def _b64url(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except Exception:
        return ""


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]{2,}", " ", s)).strip()


def _extract_html_text(payload: dict) -> tuple[str, str]:
    """Walk a Gmail payload tree; return (raw_html, plain_text).

    raw_html is the original HTML (for rendering with images/links); plain_text
    prefers text/plain, falling back to HTML stripped to text (for context)."""
    plain: list[str] = []
    html_parts: list[str] = []

    def walk(p: dict) -> None:
        data = (p.get("body") or {}).get("data")
        mime = p.get("mimeType", "")
        if data:
            if mime == "text/plain":
                plain.append(_b64url(data))
            elif mime == "text/html":
                html_parts.append(_b64url(data))
        for child in p.get("parts", []) or []:
            walk(child)

    walk(payload or {})
    raw_html = "\n".join(html_parts).strip()
    text = "\n".join(plain).strip() if plain else _strip_html(raw_html)
    return raw_html, text


# --- Calendar ----------------------------------------------------------------

def calendar_list(start_iso: str | None = None, end_iso: str | None = None,
                  max_results: int = 25) -> list[dict[str, Any]]:
    """List calendar events in [start, end). Defaults to today (local)."""
    if start_iso is None or end_iso is None:
        today = _dt.date.today()
        start = _dt.datetime.combine(today, _dt.time.min).astimezone()
        end = start + _dt.timedelta(days=1)
        start_iso, end_iso = start.isoformat(), end.isoformat()
    res = mcp_google.call_tool("calendar_event_list", {
        "time_min": start_iso, "time_max": end_iso,
        "single_events": True, "max_results": max_results,
    })
    items = res.get("items", []) if isinstance(res, dict) else []
    out = []
    for e in items:
        start = e.get("start", {})
        end = e.get("end") or {}
        attendees = [
            {"email": a.get("email"), "name": a.get("displayName") or a.get("email"),
             "status": a.get("responseStatus"), "organizer": bool(a.get("organizer")),
             "optional": bool(a.get("optional"))}
            for a in e.get("attendees", []) if a.get("email")
        ]
        desc = e.get("description") or ""
        # Strip HTML if the description is HTML (Google sometimes returns markup).
        if "<" in desc and ">" in desc:
            desc = _strip_html(desc)
        out.append({
            "id": e.get("id"),
            "summary": e.get("summary", "(no title)"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "all_day": bool(start.get("date") and not start.get("dateTime")),
            "color_id": e.get("colorId"),
            "location": e.get("location"),
            "description": desc[:4000],
            "organizer": (e.get("organizer") or {}).get("email"),
            "attendees": attendees,
            "hangout": e.get("hangoutLink"),
        })
    return out


def calendar_set_color(event_id: str, color_id: str) -> dict[str, Any]:
    """Set an event's color (category). send_updates=none so guests aren't
    notified by a recolour. EFFECTING."""
    mcp_google.call_tool("calendar_event_update", {
        "event_id": event_id, "color_id": color_id, "send_updates": "none",
    })
    return {"event_id": event_id, "color_id": color_id}


# --- Gmail (read) ------------------------------------------------------------

def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def gmail_list_messages(query: str = "in:inbox", max_results: int = 25) -> list[dict[str, Any]]:
    """List messages matching a Gmail query (headers + snippet)."""
    res = mcp_google.call_tool("gmail_message_list", {"q": query, "max_results": max_results})
    msgs = res.get("messages", res.get("items", [])) if isinstance(res, dict) else []
    out = []
    for m in msgs:
        # gmail_message_list may already include headers/snippet; normalize.
        headers = m.get("payload", {}).get("headers", []) if m.get("payload") else m.get("headers", [])
        out.append({
            "id": m.get("id"),
            "thread_id": m.get("threadId") or m.get("thread_id"),
            "subject": m.get("subject") or _header(headers, "Subject") or "(no subject)",
            "from": m.get("from") or _header(headers, "From"),
            "date": m.get("date") or _header(headers, "Date"),
            "snippet": m.get("snippet", ""),
            "label_ids": m.get("labelIds") or m.get("label_ids", []),
        })
    return out


def gmail_get_message(message_id: str) -> dict[str, Any]:
    """Full message: headers, decoded body (HTML + text), current label ids."""
    res = mcp_google.call_tool("gmail_message_get", {"message_id": message_id, "format": "full"})
    if not isinstance(res, dict):
        return {"id": message_id, "body_text": str(res), "body_html": ""}
    msg = res.get("message", res)  # the API wraps the message under "message"
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    raw_html, text = _extract_html_text(payload)
    if not text:
        text = msg.get("snippet", "")
    return {
        "id": message_id,
        "thread_id": msg.get("threadId") or msg.get("thread_id"),
        "subject": _header(headers, "Subject") or "(no subject)",
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "date": _header(headers, "Date"),
        "snippet": msg.get("snippet", ""),
        "label_ids": msg.get("labelIds") or msg.get("label_ids", []),
        "body_html": raw_html[:200000],
        "body_text": (text or "")[:50000],
    }


# --- Gmail (threads / conversations) -----------------------------------------

def gmail_thread_list(query: str = "in:inbox", max_results: int = 100) -> list[dict[str, Any]]:
    """List conversations (threads) matching a query. Newest-first."""
    res = mcp_google.call_tool("gmail_thread_list", {"q": query, "max_results": max_results})
    items = res.get("items", res.get("threads", [])) if isinstance(res, dict) else []
    return [
        {
            "thread_id": t.get("id"),
            "subject": t.get("subject") or "(no subject)",
            "from": t.get("from", ""),
            "snippet": t.get("snippet", ""),
            "message_count": t.get("messageCount", 1),
        }
        for t in items if t.get("id")
    ]


def gmail_get_thread(thread_id: str) -> dict[str, Any]:
    """A conversation's per-message metadata (no bodies — those are fetched
    lazily on open). internal_date is epoch ms. Used by the sync pass."""
    res = mcp_google.call_tool("gmail_thread_get", {"thread_id": thread_id, "format": "metadata"})
    th = res.get("thread", res) if isinstance(res, dict) else {}
    raw = th.get("messages", []) if isinstance(th, dict) else []
    msgs = []
    for m in raw:
        headers = (m.get("payload") or {}).get("headers", [])
        msgs.append({
            "id": m.get("id"),
            "from": _header(headers, "From"),
            "to": _header(headers, "To"),
            "date": _header(headers, "Date"),
            "subject": _header(headers, "Subject"),
            "snippet": m.get("snippet", ""),
            "internal_date": m.get("internalDate"),
            "label_ids": m.get("labelIds") or [],
        })
    return {
        "thread_id": thread_id,
        "messages": msgs,
        "latest_internal_date": msgs[-1]["internal_date"] if msgs else None,
    }


def gmail_archive_thread(thread_id: str) -> dict[str, Any]:
    """Archive a conversation in Gmail (remove the INBOX label). EFFECTING."""
    mcp_google.call_tool("gmail_thread_modify", {
        "thread_id": thread_id, "remove_label_ids": ["INBOX"],
    })
    return {"thread_id": thread_id, "archived": True}


def gmail_send(to: str, subject: str, body: str,
               in_reply_to_message_id: str | None = None) -> dict[str, Any]:
    """SEND an email (in-thread when replying). EFFECTING + irreversible."""
    args: dict[str, Any] = {"to": to, "subject": subject, "body": body}
    if in_reply_to_message_id:
        args["reply_to_message_id"] = in_reply_to_message_id
    mcp_google.call_tool("gmail_message_send", args)
    return {"sent": True, "to": to}


def thread_latest_epoch(thread_id: str) -> int | None:
    """Epoch SECONDS of a thread's latest message — the 'before:' paging cursor."""
    res = mcp_google.call_tool("gmail_thread_get", {"thread_id": thread_id, "format": "minimal"})
    th = res.get("thread", res) if isinstance(res, dict) else {}
    raw = th.get("messages", []) if isinstance(th, dict) else []
    ms = raw[-1].get("internalDate") if raw else None
    return int(ms) // 1000 if ms else None


# --- Drive / Docs ------------------------------------------------------------

def drive_find_meeting_doc(name_contains: str, after_iso: str | None = None,
                           max_results: int = 10) -> list[dict[str, Any]]:
    """Find Google Docs by name fragment (and optional modifiedTime lower bound)."""
    args: dict[str, Any] = {"query": name_contains, "max_results": max_results,
                            "file_types": ["document"]}
    if after_iso:
        args["additional_filters"] = {"modifiedTime_after": after_iso}
    res = mcp_google.call_tool("drive_search", args)
    files = res.get("files", res.get("items", [])) if isinstance(res, dict) else []
    return [
        {"id": f.get("id"), "name": f.get("name"),
         "modifiedTime": f.get("modifiedTime"), "webViewLink": f.get("webViewLink")}
        for f in files
    ]


def docs_export(document_id: str) -> dict[str, Any]:
    """Export a Google Doc as markdown via the MCP per-doc export.

    docs_document_export writes per-tab markdown to a directory; we read it back
    and concatenate. (docs_document_export_as_markdown returns flat text but is
    omitted here for the larger tabbed docs case.)
    """
    out_dir = tempfile.mkdtemp(prefix="saco_doc_")
    mcp_google.call_tool("docs_document_export", {"document_id": document_id, "output_dir": out_dir})
    parts = []
    for p in sorted(Path(out_dir).rglob("content.md")):
        parts.append(p.read_text(encoding="utf-8"))
    if not parts:  # fallback to flat export
        flat = mcp_google.call_tool("docs_document_export_as_markdown", {"document_id": document_id})
        text = flat.get("markdown", "") if isinstance(flat, dict) else str(flat)
        parts = [text]
    return {"id": document_id, "markdown": "\n\n".join(parts).strip()[:60000]}
