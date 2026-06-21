"""Gmail effecting tools over the MCP server — draft creation only.

Reuses the already-authenticated dbexec Google MCP server. EFFECTING, gated by
server/approval.py.

Label write-back lives in server/lakebase.py instead of Gmail: the dbexec Google
MCP exposes no labels.list/create, so the taxonomy is stored in Lakebase
(Databricks Postgres), not as Gmail labels.

HARD RULE: drafts only — nothing here sends mail (gmail_draft_create, not send).
"""
from __future__ import annotations

from typing import Any

from server import mcp_google


def gmail_create_draft(to: str, subject: str, body: str,
                       thread_id: str | None = None,
                       in_reply_to_message_id: str | None = None) -> dict[str, Any]:
    """Create a Gmail DRAFT (never sends). EFFECTING."""
    args: dict[str, Any] = {"to": to, "subject": subject, "body": body}
    if in_reply_to_message_id:
        args["reply_to_message_id"] = in_reply_to_message_id
    res = mcp_google.call_tool("gmail_draft_create", args)
    draft_id = res.get("id") or res.get("draft_id") if isinstance(res, dict) else None
    return {"draft_id": draft_id, "to": to, "subject": subject}
