"""Agent routes: stream the loop over SSE; resolve approvals."""
from __future__ import annotations

import json


from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sacopilot.backend import agent, approval

from sacopilot.backend.core import create_router
router = create_router()


class MessageRequest(BaseModel):
    message: str
    history: list[dict] | None = None


@router.post("/agent/message")
async def agent_message(req: MessageRequest) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in agent.run(req.message, req.history):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:  # never drop the stream silently
            yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {e}'})}\n\n"
        yield "data: {\"type\": \"end\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class ApprovalDecision(BaseModel):
    id: str
    decision: str  # "approve" | "reject"
    edited_args: dict | None = None


@router.post("/agent/approve")
async def agent_approve(req: ApprovalDecision) -> dict:
    ok = approval.manager.resolve(req.id, req.decision, req.edited_args)
    return {"resolved": ok}


@router.get("/agent/pending")
async def agent_pending() -> dict:
    return {"pending": approval.manager.list_pending()}
