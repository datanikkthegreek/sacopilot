"""Approval gate for effecting tools.

Effecting tools (Gmail label writes, draft creation, vault commits) never run
without explicit user OK. The agent loop, instead of executing them, registers
a *pending approval* carrying the human-readable proposal, then awaits the
user's decision (delivered via the /agent/approve endpoint). Read tools bypass
this entirely.

This is enforced here, in code — not via prompting.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

# Tools that mutate Gmail / the vault / create drafts. Everything else is read.
EFFECTING_TOOLS = {
    "gmail_apply_labels",
    "gmail_ensure_labels",
    "gmail_create_draft",
    "commit_writes",
}


@dataclass
class PendingApproval:
    id: str
    tool: str
    args: dict[str, Any]
    summary: str                       # human-readable proposal for the UI
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: str | None = None        # "approve" | "reject"
    edited_args: dict | None = None     # user may tweak before approving


class ApprovalManager:
    """Holds pending approvals keyed by id; the loop awaits, the API resolves."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def is_effecting(self, tool: str) -> bool:
        return tool in EFFECTING_TOOLS

    def create(self, tool: str, args: dict, summary: str) -> PendingApproval:
        pa = PendingApproval(id=str(uuid.uuid4()), tool=tool, args=args, summary=summary)
        self._pending[pa.id] = pa
        return pa

    async def wait(self, pa: PendingApproval) -> PendingApproval:
        await pa.event.wait()
        return pa

    def resolve(self, approval_id: str, decision: str, edited_args: dict | None = None) -> bool:
        pa = self._pending.get(approval_id)
        if not pa:
            return False
        pa.decision = decision
        pa.edited_args = edited_args
        pa.event.set()
        return True

    def pop(self, approval_id: str) -> None:
        self._pending.pop(approval_id, None)

    def list_pending(self) -> list[dict]:
        return [
            {"id": p.id, "tool": p.tool, "summary": p.summary, "args": p.args}
            for p in self._pending.values() if not p.event.is_set()
        ]


# Module-level singleton used by the agent loop + API.
manager = ApprovalManager()


def summarize(tool: str, args: dict) -> str:
    """Human-readable one-liner describing what an effecting call will do."""
    if tool == "gmail_apply_labels":
        add = ", ".join(args.get("add", []) or [])
        rem = ", ".join(args.get("remove", []) or [])
        parts = []
        if add:
            parts.append(f"add [{add}]")
        if rem:
            parts.append(f"remove [{rem}]")
        return f"Apply labels to message {args.get('message_id','?')[:12]}: " + "; ".join(parts)
    if tool == "gmail_ensure_labels":
        return "Create the SA Copilot label tree in Gmail (one-time)."
    if tool == "gmail_create_draft":
        return f"Create Gmail DRAFT to {args.get('to','?')} — \"{args.get('subject','')}\" (not sent)."
    if tool == "commit_writes":
        n = len(args.get("diffs", []) or [])
        return f"Write {n} approved change(s) to the Obsidian vault."
    return f"{tool}({', '.join(args)})"
