"""The agent loop — manual Anthropic tool-use loop with approval gating.

Streams events (text, tool_use, tool_result, approval_request, done) as dicts
for the SSE route. Effecting tools pause: the loop registers a PendingApproval
and awaits resolution before executing (or skips on reject). Read tools run
inline. Model: config.MODEL (databricks-claude-opus-4-8 on the gateway),
adaptive thinking.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

import anthropic

from sacopilot.backend import config, approval
from sacopilot.backend.tools import registry

SYSTEM = """You are the SA Copilot for a Databricks Solutions Architect working the Bosch account.

You help with drafting and meeting capture in the user's voice (reading mail/
calendar/vault for context, creating Gmail drafts, capturing meeting notes).
Email classification is handled by a separate cockpit flow, not by you.

Rules:
- Effecting actions (creating drafts, committing vault notes) require user approval; just call the tool — the system will pause for the user. Don't ask in text first.
- Drafts only; you never send email.
- Be concise. Report what you did, not what you're about to do."""

_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


async def run(user_message: str, history: list[dict] | None = None
              ) -> AsyncGenerator[dict, None]:
    """Run the agent loop, yielding event dicts. Pauses for approvals."""
    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": user_message})
    client = _anthropic()

    while True:
        # One model turn (sync SDK call run off the event loop).
        try:
            resp = await asyncio.to_thread(
                client.messages.create,
                model=config.MODEL,
                max_tokens=8000,
                thinking={"type": "adaptive"},
                system=SYSTEM,
                tools=registry.TOOLS,
                messages=messages,
            )
        except Exception as e:  # surface API errors to the UI instead of dying
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
            return

        # Emit assistant text.
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                yield {"type": "text", "text": block.text}

        if resp.stop_reason != "tool_use":
            yield {"type": "done", "stop_reason": resp.stop_reason}
            return

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []

        for block in resp.content:
            if block.type != "tool_use":
                continue
            name, args, tuid = block.name, dict(block.input), block.id
            yield {"type": "tool_use", "tool": name, "args": args}

            # Effecting tools pause for approval.
            if approval.manager.is_effecting(name):
                pa = approval.manager.create(name, args, approval.summarize(name, args))
                yield {"type": "approval_request", "id": pa.id, "tool": name,
                       "summary": pa.summary, "args": args}
                await approval.manager.wait(pa)
                approval.manager.pop(pa.id)
                if pa.decision != "approve":
                    yield {"type": "tool_result", "tool": name, "skipped": True}
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tuid,
                        "content": "User rejected this action; it was not performed.",
                    })
                    continue
                args = pa.edited_args or args  # user may have tweaked

            # Execute (read tools, or approved effecting tools).
            try:
                result = await asyncio.to_thread(registry.call_tool, name, args)
                yield {"type": "tool_result", "tool": name, "result": result}
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tuid,
                    "content": _to_text(result),
                })
            except Exception as e:
                yield {"type": "tool_result", "tool": name, "error": str(e)}
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tuid,
                    "content": f"Error: {type(e).__name__}: {e}", "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})


def _to_text(result: Any) -> str:
    import json
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)
