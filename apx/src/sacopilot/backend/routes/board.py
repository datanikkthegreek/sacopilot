"""Action Board (Kanban) routes — prioritised todos in Lakebase."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from pydantic import BaseModel

from sacopilot.backend import lakebase, salesforce, taxonomy
from sacopilot.backend.core import create_router

router = create_router()

STATUSES = ["Open", "This week", "Next week", "In progress", "Completed"]
TYPES = ["Bosch", "Internal", "Enablement"]
PRIORITIES = ["0", "1", "2"]


@router.get("/board/todos")
def board_todos() -> dict:
    try:
        return {"todos": lakebase.list_todos()}
    except Exception as e:
        raise HTTPException(503, f"Lakebase unavailable: {e}")


@router.get("/board/meta")
def board_meta() -> dict:
    use_cases: list[dict] = []
    try:  # best-effort; the board works even if Salesforce is down/un-authed
        use_cases = [{"id": u["id"], "name": u["name"]} for u in salesforce.list_ucos()]
    except Exception:
        use_cases = []
    return {"statuses": STATUSES, "types": TYPES, "priorities": PRIORITIES,
            "bu": taxonomy.BU, "use_cases": use_cases}


class TodoIn(BaseModel):
    title: str = "(untitled)"
    description: str | None = None
    status: str = "Open"
    priority: str = "2"
    estimate_hours: float | None = None
    type: str | None = None
    use_case_id: str | None = None
    use_case_name: str | None = None
    bu: str | None = None
    project: str | None = None
    tags: list[str] = []


@router.post("/board/todos")
def create_todo(body: TodoIn) -> dict:
    if body.status not in STATUSES:
        raise HTTPException(422, f"invalid status {body.status!r}")
    try:
        return lakebase.create_todo(body.model_dump(), uuid.uuid4().hex)
    except Exception as e:
        raise HTTPException(503, f"Could not create todo: {e}")


class TodoPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    estimate_hours: float | None = None
    type: str | None = None
    use_case_id: str | None = None
    use_case_name: str | None = None
    bu: str | None = None
    project: str | None = None
    tags: list[str] | None = None


@router.put("/board/todos/{todo_id}")
def update_todo(todo_id: str, body: TodoPatch) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in STATUSES:
        raise HTTPException(422, f"invalid status {fields['status']!r}")
    try:
        return lakebase.update_todo(todo_id, fields)
    except Exception as e:
        raise HTTPException(503, f"Could not update todo: {e}")


@router.delete("/board/todos/{todo_id}")
def delete_todo(todo_id: str) -> dict:
    try:
        return {"deleted": lakebase.delete_todo(todo_id)}
    except Exception as e:
        raise HTTPException(503, f"Could not delete todo: {e}")
