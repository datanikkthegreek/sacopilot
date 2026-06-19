"""Google read tools (Calendar / Gmail / Drive / Docs).

Read-only operations only. Label write-back + draft creation (effecting) live
in server/tools/gmail_write.py (Phase 3). All functions return plain dicts/lists
ready to hand to the agent or the frontend.
"""
from __future__ import annotations

import base64
import datetime as _dt
import re
from typing import Any

from server import google_client

# --- Calendar ----------------------------------------------------------------

def calendar_list(start_iso: str | None = None, end_iso: str | None = None,
                  max_results: int = 25) -> list[dict[str, Any]]:
    """List calendar events in [start, end). Defaults to today (local)."""
    if start_iso is None or end_iso is None:
        today = _dt.date.today()
        start = _dt.datetime.combine(today, _dt.time.min).astimezone()
        end = start + _dt.timedelta(days=1)
        start_iso, end_iso = start.isoformat(), end.isoformat()
    resp = (
        google_client.calendar()
        .events()
        .list(calendarId="primary", timeMin=start_iso, timeMax=end_iso,
              singleEvents=True, orderBy="startTime", maxResults=max_results)
        .execute()
    )
    out = []
    for e in resp.get("items", []):
        start = e.get("start", {})
        out.append({
            "id": e.get("id"),
            "summary": e.get("summary", "(no title)"),
            "start": start.get("dateTime") or start.get("date"),
            "end": (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date"),
            "attendees": [a.get("email") for a in e.get("attendees", []) if a.get("email")],
            "hangout": e.get("hangoutLink"),
        })
    return out


# --- Gmail (read) ------------------------------------------------------------

def gmail_list_messages(query: str = "in:inbox", max_results: int = 25) -> list[dict[str, Any]]:
    """List message ids + thread ids matching a Gmail search query.

    For incremental classification, callers pass a query like
    `in:inbox -label:Type/Action -label:Type/Informative ...` or an `after:`
    watermark. This returns headers only; use gmail_get_message for bodies.
    """
    svc = google_client.gmail()
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    out = []
    for m in resp.get("messages", []):
        meta = (
            svc.users().messages()
            .get(userId="me", id=m["id"], format="metadata",
                 metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
        out.append({
            "id": m["id"],
            "thread_id": meta.get("threadId"),
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": meta.get("snippet", ""),
            "label_ids": meta.get("labelIds", []),
        })
    return out


def _decode_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """Prefer text/plain; fall back to stripped text/html; recurse multipart."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        return _decode_part(payload)
    if mime == "text/html":
        html = _decode_part(payload)
        return re.sub(r"<[^>]+>", " ", html)
    text = ""
    for part in payload.get("parts", []) or []:
        text += _extract_body(part)
        if len(text) > 20000:
            break
    return text


def gmail_get_message(message_id: str) -> dict[str, Any]:
    """Full message: headers, decoded body text, current label ids."""
    svc = google_client.gmail()
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    body = _extract_body(payload).strip()
    return {
        "id": message_id,
        "thread_id": msg.get("threadId"),
        "subject": headers.get("Subject", "(no subject)"),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "snippet": msg.get("snippet", ""),
        "label_ids": msg.get("labelIds", []),
        "body": body[:20000],
    }


# --- Drive / Docs ------------------------------------------------------------

def drive_find_meeting_doc(name_contains: str, after_iso: str | None = None,
                           max_results: int = 10) -> list[dict[str, Any]]:
    """Find Google Docs (e.g. Gemini meeting notes) by name fragment.

    Matching is by name; callers refine by meeting time via after_iso
    (modifiedTime lower bound) per the spec's name+time matching rule.
    """
    q_parts = ["mimeType='application/vnd.google-apps.document'", "trashed=false"]
    if name_contains:
        safe = name_contains.replace("'", "\\'")
        q_parts.append(f"name contains '{safe}'")
    if after_iso:
        q_parts.append(f"modifiedTime > '{after_iso}'")
    resp = (
        google_client.drive().files()
        .list(q=" and ".join(q_parts), orderBy="modifiedTime desc",
              pageSize=max_results, fields="files(id,name,modifiedTime,webViewLink)")
        .execute()
    )
    return resp.get("files", [])


def docs_export(document_id: str) -> dict[str, Any]:
    """Export a Google Doc as plain markdown-ish text (flat).

    For the large tabbed master docs we use the MCP per-tab export elsewhere;
    this is the lightweight in-app path for a single meeting doc.
    """
    doc = google_client.docs().documents().get(documentId=document_id).execute()
    lines: list[str] = []
    for el in doc.get("body", {}).get("content", []):
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(
            r.get("textRun", {}).get("content", "")
            for r in para.get("elements", [])
        )
        style = para.get("paragraphStyle", {}).get("namedStyleType", "")
        if style.startswith("HEADING") and text.strip():
            level = "#" * (int(style.split("_")[-1]) if style.split("_")[-1].isdigit() else 2)
            lines.append(f"{level} {text.strip()}")
        else:
            lines.append(text.rstrip("\n"))
    return {
        "id": document_id,
        "title": doc.get("title", ""),
        "markdown": "\n".join(lines).strip(),
    }
