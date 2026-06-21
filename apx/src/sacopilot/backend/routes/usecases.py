"""Use-Cases cockpit routes: list/read Salesforce UCOs, generate artifacts
(Next Steps / Onboarding) via the ported skill templates, and write back."""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel

from sacopilot.backend import salesforce, usecase_gen
from sacopilot.backend.core import create_router

router = create_router()


def _today_de() -> str:
    return _dt.datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d/%m/%Y")


@router.get("/usecases")
def usecases_list(account: str = "Bosch Global", prefix: str = "[NS]") -> dict:
    try:
        return {"ucos": salesforce.list_ucos(account=account, prefix=prefix)}
    except Exception as e:
        raise HTTPException(503, f"Salesforce: {e}")


@router.get("/usecases/{uco_id}")
def usecase_detail(uco_id: str) -> dict:
    try:
        uco = salesforce.get_uco(uco_id)
    except Exception as e:
        raise HTTPException(503, f"Salesforce: {e}")
    uco["onboarding_allowed"] = usecase_gen.onboarding_allowed(uco.get("stage"))
    return uco


class GenerateIn(BaseModel):
    artifact: str  # "next_steps" | "onboarding"
    prompt: str = ""


@router.post("/usecases/{uco_id}/generate")
def usecase_generate(uco_id: str, body: GenerateIn) -> dict:
    try:
        uco = salesforce.get_uco(uco_id)
    except Exception as e:
        raise HTTPException(503, f"Salesforce: {e}")
    try:
        res = usecase_gen.generate(body.artifact, uco, _today_de(), body.prompt)
    except Exception as e:
        raise HTTPException(502, f"Generation failed: {e}")
    return {"artifact": body.artifact, "text": res["text"], "feedback": res["feedback"]}


class UpdateIn(BaseModel):
    next_steps: str | None = None
    onboarding: str | None = None


@router.put("/usecases/{uco_id}")
def usecase_update(uco_id: str, body: UpdateIn) -> dict:
    fields = {k: v for k, v in {"next_steps": body.next_steps, "onboarding": body.onboarding}.items() if v is not None}
    if not fields:
        raise HTTPException(422, "nothing to update")
    try:
        return salesforce.update_uco(uco_id, fields)
    except Exception as e:
        raise HTTPException(502, f"Salesforce update failed: {e}")
