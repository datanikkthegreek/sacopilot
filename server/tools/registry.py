"""Tool registry: Anthropic tool schemas + name -> callable dispatch.

Keeps the agent's tool surface small and explicit (spec ~11 tools). Read tools
run inline; effecting tools are gated by the approval layer in the agent loop.
"""
from __future__ import annotations

from typing import Any, Callable

from server import taxonomy
from server.tools import classify as _classify
from server.tools import google as _g
from server.tools import gmail_write as _gw
from server.tools import vault as _v

# --- Anthropic tool schemas --------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "name": "calendar_list",
        "description": "List the user's Google Calendar events. Defaults to today if no range given.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_iso": {"type": "string", "description": "ISO start datetime (optional)"},
                "end_iso": {"type": "string", "description": "ISO end datetime (optional)"},
            },
        },
    },
    {
        "name": "gmail_list_messages",
        "description": "List Gmail messages matching a search query (headers + snippet only). Use Gmail query syntax, e.g. 'in:inbox', 'after:2026/06/01', '-label:Type/Action'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
        },
    },
    {
        "name": "gmail_get_message",
        "description": "Get one Gmail message in full: headers, decoded body, current labels.",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "classify_email",
        "description": "Classify an email into the 6-facet taxonomy (Type/Org/Prio/DBX/Bosch/BU + confidence). Returns facets and the Gmail label names to apply.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "sender": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["subject", "sender", "body"],
        },
    },
    {
        "name": "gmail_ensure_labels",
        "description": "Create the SA Copilot nested label tree in Gmail (one-time, idempotent). EFFECTING.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_apply_labels",
        "description": "Apply/remove labels on a Gmail message by label name (e.g. 'Type/Action', 'BU/PT'). Writes back to Gmail. EFFECTING.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "add": {"type": "array", "items": {"type": "string"}},
                "remove": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_create_draft",
        "description": "Create a Gmail draft (NEVER sends). Use the user's voice. EFFECTING.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "thread_id": {"type": "string"},
                "in_reply_to_message_id": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "drive_find_meeting_doc",
        "description": "Find a Google Doc (e.g. Gemini meeting notes/transcript) by name fragment; optionally bounded by modifiedTime (after_iso) for name+time matching.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name_contains": {"type": "string"},
                "after_iso": {"type": "string"},
            },
            "required": ["name_contains"],
        },
    },
    {
        "name": "docs_export",
        "description": "Export a Google Doc as markdown text.",
        "input_schema": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
    {
        "name": "vault_search",
        "description": "Search the Obsidian vault (notes/contacts/projects) by substring. Read-only context.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
            "required": ["query"],
        },
    },
    {
        "name": "vault_read",
        "description": "Read a vault note by vault-relative path. Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"rel_path": {"type": "string"}},
            "required": ["rel_path"],
        },
    },
    {
        "name": "vault_recent_meetings",
        "description": "List the most recent meeting notes for a Bosch BU code (e.g. PT). Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"bu": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["bu"],
        },
    },
    {
        "name": "propose_meeting_note",
        "description": "Propose a new/updated meeting note (returns a diff; does NOT write). bu=BU code, filename='YYYY-MM-DD - topic', project optional (subfolder).",
        "input_schema": {
            "type": "object",
            "properties": {
                "bu": {"type": "string"}, "filename": {"type": "string"},
                "content": {"type": "string"}, "project": {"type": "string"},
            },
            "required": ["bu", "filename", "content"],
        },
    },
    {
        "name": "propose_contact_update",
        "description": "Propose a new/updated contact note (returns a diff; does NOT write).",
        "input_schema": {
            "type": "object",
            "properties": {"bu": {"type": "string"}, "name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["bu", "name", "content"],
        },
    },
    {
        "name": "commit_writes",
        "description": "Apply approved vault proposals (list of {path,new_content}). EFFECTING. Meetings only.",
        "input_schema": {
            "type": "object",
            "properties": {"diffs": {"type": "array", "items": {"type": "object"}}},
            "required": ["diffs"],
        },
    },
]


# --- Dispatch ----------------------------------------------------------------
def _classify_tool(subject: str, sender: str, body: str) -> dict:
    from server import state
    return _classify.classify_email(subject, sender, body, examples=state.load_corrections())


DISPATCH: dict[str, Callable[..., Any]] = {
    "calendar_list": _g.calendar_list,
    "gmail_list_messages": _g.gmail_list_messages,
    "gmail_get_message": _g.gmail_get_message,
    "classify_email": _classify_tool,
    "gmail_ensure_labels": _gw.gmail_ensure_labels,
    "gmail_apply_labels": _gw.gmail_apply_labels,
    "gmail_create_draft": _gw.gmail_create_draft,
    "drive_find_meeting_doc": _g.drive_find_meeting_doc,
    "docs_export": _g.docs_export,
    "vault_search": _v.vault_search,
    "vault_read": _v.vault_read,
    "vault_recent_meetings": _v.vault_recent_meetings,
    "propose_meeting_note": _v.propose_meeting_note,
    "propose_contact_update": _v.propose_contact_update,
    "commit_writes": _v.commit_writes,
}


def call_tool(name: str, args: dict) -> Any:
    if name not in DISPATCH:
        raise ValueError(f"unknown tool: {name}")
    return DISPATCH[name](**args)
