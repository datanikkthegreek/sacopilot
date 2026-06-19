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
}


def call_tool(name: str, args: dict) -> Any:
    if name not in DISPATCH:
        raise ValueError(f"unknown tool: {name}")
    return DISPATCH[name](**args)
