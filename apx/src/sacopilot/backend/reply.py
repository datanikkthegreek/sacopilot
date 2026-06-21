"""Reply drafting: full-thread context + Glean + the user's voice → Gmail draft.

Pulls the whole conversation from the Lakebase cache (fetching any missing
bodies once), searches Glean for relevant internal context (best-effort), reads
the user's voice profile, asks Claude (via the Databricks gateway) to draft a
reply, and saves it as a Gmail DRAFT (never sends).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import anthropic

from sacopilot.backend import config, lakebase, mcp_glean
from sacopilot.backend.tools import gmail_write, google

_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _voice_profile() -> str:
    try:
        return Path(config.VOICE_PROFILE_PATH).read_text()[:4000]
    except Exception:
        return ""


def _ensure_bodies(thread_id: str, msgs: list[dict]) -> list[dict]:
    for m in msgs:
        if not m.get("body_text") and not m.get("body_html"):
            try:
                full = google.gmail_get_message(m["message_id"])
                m["body_text"], m["body_html"] = full["body_text"], full["body_html"]
                lakebase.store_body(m["message_id"], full["body_html"], full["body_text"])
            except Exception:
                m["body_text"] = m.get("snippet") or ""
    return msgs


SYSTEM = """You are drafting an email reply on behalf of a Databricks Solutions Architect working the Bosch account.

Write the reply in the user's voice (profile below). Be warm and pragmatic: open with a human touch, then get to the point; offer options rather than dictate; end with a clear, answerable question. No em dashes, no corporate filler, no AI-slop. Mirror the language of the latest message (German or English). Keep it concise.

Use the conversation history for context and the Glean snippets for facts; cite nothing inline. Output ONLY the email body text (no subject line, no "Here is the draft", no signature block beyond a short sign-off like "Best, Nikk" / "Gruss Niko")."""


def draft_reply(thread_id: str) -> dict[str, Any]:
    msgs = lakebase.get_thread_messages(thread_id)
    if not msgs:
        raise RuntimeError("thread not in cache; run sync first")
    msgs = _ensure_bodies(thread_id, msgs)
    latest = msgs[-1]

    history = "\n\n---\n\n".join(
        f"From: {m['from_addr']}\nDate: {m['date_str']}\n\n{(m['body_text'] or m['snippet'] or '').strip()[:6000]}"
        for m in msgs
    )[:24000]

    subject = latest.get("subject") or "(no subject)"
    glean_query = re.sub(r"^(re|fwd|aw|wg):\s*", "", subject, flags=re.I).strip() or subject
    sources = mcp_glean.search(glean_query) if mcp_glean.is_available() else []
    glean_block = ""
    if sources:
        glean_block = "\n\nGlean context:\n" + "\n".join(
            f"- {s['title']}: {s['snippet']}" for s in sources)

    voice = _voice_profile()
    user_msg = (
        (f"User voice profile:\n{voice}\n\n" if voice else "") +
        f"Conversation (oldest first):\n{history}{glean_block}\n\n"
        f"Draft a reply to the latest message (from {latest['from_addr']})."
    )

    resp = _anthropic().messages.create(
        model=config.MODEL, max_tokens=1200, thinking={"type": "adaptive"},
        system=SYSTEM, messages=[{"role": "user", "content": user_msg}],
    )
    draft_text = "".join(b.text for b in resp.content if b.type == "text").strip()

    re_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    to = latest.get("from_addr") or ""
    saved = gmail_write.gmail_create_draft(
        to=to, subject=re_subject, body=draft_text,
        in_reply_to_message_id=latest["message_id"],
    )
    return {
        "thread_id": thread_id,
        "to": to,
        "subject": re_subject,
        "draft_text": draft_text,
        "draft_id": saved.get("draft_id"),
        "sources": sources,
        "glean_used": bool(sources),
    }
