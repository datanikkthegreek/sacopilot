"""Mail read routes for the cockpit: list inbox with taxonomy label chips."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server import google_client
from server.tools import google

router = APIRouter()

# Gmail returns label IDs on messages; we map system + our taxonomy labels to
# display names. Cache id->name once.
_id_to_name: dict[str, str] = {}


def _label_names(label_ids: list[str]) -> list[str]:
    global _id_to_name
    if not _id_to_name:
        resp = google_client.gmail().users().labels().list(userId="me").execute()
        _id_to_name = {l["id"]: l["name"] for l in resp.get("labels", [])}
    # Only surface our nested taxonomy labels (contain "/") as chips.
    return sorted(
        _id_to_name.get(lid, lid)
        for lid in label_ids
        if "/" in _id_to_name.get(lid, "")
    )


@router.get("/mail/list")
def mail_list(query: str = "in:inbox", max_results: int = 30) -> list[dict]:
    if not google_client.is_authorized():
        raise HTTPException(503, "Google not authorized. Run: uv run python -m server.google_client auth")
    msgs = google.gmail_list_messages(query=query, max_results=max_results)
    for m in msgs:
        m["labels"] = _label_names(m.pop("label_ids", []))
    return msgs
