"""Gmail effecting tools — label write-back + draft creation.

These MUTATE Gmail (labels) or create drafts. They are gated by the approval
layer (server/approval.py) so nothing applies without explicit user OK.
Gmail is the source of truth for labels: we create the nested label tree and
write assigned labels back so they show up in Gmail everywhere.

HARD RULE: drafts only. Nothing here sends mail.
"""
from __future__ import annotations

from typing import Any

from server import google_client, taxonomy

# Cache of label name -> Gmail label id (refreshed on demand).
_label_cache: dict[str, str] = {}


def _refresh_label_cache() -> dict[str, str]:
    resp = google_client.gmail().users().labels().list(userId="me").execute()
    _label_cache.clear()
    for lab in resp.get("labels", []):
        _label_cache[lab["name"]] = lab["id"]
    return _label_cache


def gmail_ensure_labels() -> dict[str, Any]:
    """Create the full nested taxonomy label tree in Gmail (idempotent).

    Gmail auto-creates parent labels (e.g. 'Type') when a child ('Type/Action')
    is made, so we only create leaves. Returns how many were created.
    """
    existing = _refresh_label_cache()
    created = []
    for name in taxonomy.every_possible_label():
        if name in existing:
            continue
        lab = (
            google_client.gmail().users().labels()
            .create(userId="me", body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            })
            .execute()
        )
        _label_cache[lab["name"]] = lab["id"]
        created.append(name)
    return {"created": created, "total_labels": len(_label_cache)}


def _name_to_id(name: str) -> str:
    if name not in _label_cache:
        _refresh_label_cache()
    if name not in _label_cache:
        # Create on the fly (e.g. a BU label not yet in the tree).
        lab = (
            google_client.gmail().users().labels()
            .create(userId="me", body={"name": name})
            .execute()
        )
        _label_cache[lab["name"]] = lab["id"]
    return _label_cache[name]


def gmail_apply_labels(message_id: str, add: list[str] | None = None,
                       remove: list[str] | None = None) -> dict[str, Any]:
    """Apply/remove labels (by NAME) on a message. Writes back to Gmail.

    EFFECTING — gated by approval. `add`/`remove` are taxonomy label names like
    'Type/Action', 'BU/PT'. Used both for first classification and for user
    corrections.
    """
    add_ids = [_name_to_id(n) for n in (add or [])]
    remove_ids = [_name_to_id(n) for n in (remove or [])]
    google_client.gmail().users().messages().modify(
        userId="me", id=message_id,
        body={"addLabelIds": add_ids, "removeLabelIds": remove_ids},
    ).execute()
    return {"message_id": message_id, "added": add or [], "removed": remove or []}


def gmail_create_draft(to: str, subject: str, body: str,
                       thread_id: str | None = None,
                       in_reply_to_message_id: str | None = None) -> dict[str, Any]:
    """Create a Gmail DRAFT (never sends). EFFECTING — gated by approval.

    If thread_id is given, the draft is attached to that thread (reply).
    """
    import base64
    from email.mime.text import MIMEText

    mime = MIMEText(body)
    mime["To"] = to
    mime["Subject"] = subject
    if in_reply_to_message_id:
        mime["In-Reply-To"] = in_reply_to_message_id
        mime["References"] = in_reply_to_message_id
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    message: dict[str, Any] = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id
    draft = (
        google_client.gmail().users().drafts()
        .create(userId="me", body={"message": message})
        .execute()
    )
    return {"draft_id": draft["id"], "to": to, "subject": subject}
