"""Salesforce access for Use Case Objects (UCOs) via the local `sf` CLI.

Local-only, like the dbexec MCP: uses the user's authenticated `sf` org. If no
org is authed, callers get a clear error pointing at /salesforce-authentication.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

_ACTIVE_STAGES = ("U1", "U2", "U3", "U4", "U5")
_FIELDS = (
    "Id, Name, Account__r.Name, Stages__c, Owner.Name, Use_Case_Description__c, "
    "Implementation_Strategy__c, Implementation_Start_Date__c, Go_Live_Date__c, "
    "Full_Production_Date__c, Implementation_Notes__c, Demand_Plan_Next_Steps__c"
)

_org: str | None = None


def _run(args: list[str]) -> dict:
    out = subprocess.run(args, capture_output=True, text=True)
    # `sf` may prepend a "Warning:" line before JSON; find the JSON start.
    txt = out.stdout
    i = txt.find("{")
    if i < 0:
        raise RuntimeError(out.stderr.strip()[:300] or "sf returned no JSON")
    d = json.loads(txt[i:])
    # sf reports errors as JSON with status!=0 / name=="Error" — surface them
    # (e.g. expired token) instead of silently returning empty results.
    if d.get("status", 0) != 0 or d.get("name") == "Error":
        msg = d.get("message", "Salesforce CLI error")
        if "token" in msg.lower() or "session" in msg.lower() or "auth" in msg.lower():
            msg += " — run /salesforce-authentication (sf org login web)."
        raise RuntimeError(msg)
    return d


def _target_org() -> str:
    global _org
    if _org:
        return _org
    try:
        d = _run(["sf", "org", "display", "--json"])
        _org = d.get("result", {}).get("username")
    except Exception:
        _org = None
    if not _org:
        try:
            d = _run(["sf", "org", "list", "--json"])
            orgs = d.get("result", {}).get("nonScratchOrgs", [])
            _org = orgs[0]["username"] if orgs else None
        except Exception:
            _org = None
    if not _org:
        raise RuntimeError("No Salesforce org authenticated. Run /salesforce-authentication (sf org login).")
    return _org


def _query(soql: str) -> list[dict]:
    d = _run(["sf", "data", "query", "--target-org", _target_org(), "--json", "--query", soql])
    return d.get("result", {}).get("records", [])


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def list_ucos(account: str = "Bosch Global", prefix: str = "[NS]") -> list[dict[str, Any]]:
    stages = ",".join(f"'{s}'" for s in _ACTIVE_STAGES)
    soql = (
        f"SELECT Id, Name, Stages__c, Account__r.Name, Owner.Name FROM UseCase__c "
        f"WHERE Account__r.Name LIKE '%{_esc(account)}%' AND Name LIKE '{_esc(prefix)}%' "
        f"AND Stages__c IN ({stages}) ORDER BY Name"
    )
    return [
        {"id": r.get("Id"), "name": r.get("Name"), "stage": r.get("Stages__c"),
         "account": (r.get("Account__r") or {}).get("Name"),
         "owner": (r.get("Owner") or {}).get("Name")}
        for r in _query(soql)
    ]


def get_uco(uco_id: str) -> dict[str, Any]:
    rows = _query(f"SELECT {_FIELDS} FROM UseCase__c WHERE Id = '{_esc(uco_id)}'")
    if not rows:
        raise RuntimeError(f"UCO {uco_id} not found")
    r = rows[0]
    return {
        "id": r.get("Id"), "name": r.get("Name"), "stage": r.get("Stages__c"),
        "account": (r.get("Account__r") or {}).get("Name"),
        "owner": (r.get("Owner") or {}).get("Name"),
        "description": r.get("Use_Case_Description__c"),
        "strategy": r.get("Implementation_Strategy__c"),
        "start_date": r.get("Implementation_Start_Date__c"),
        "go_live_date": r.get("Go_Live_Date__c"),
        "full_prod_date": r.get("Full_Production_Date__c"),
        "next_steps": r.get("Demand_Plan_Next_Steps__c") or "",
        "onboarding": r.get("Implementation_Notes__c") or "",
    }


_FIELD_MAP = {"next_steps": "Demand_Plan_Next_Steps__c", "onboarding": "Implementation_Notes__c"}


def update_uco(uco_id: str, fields: dict[str, str]) -> dict[str, Any]:
    """Update Next Steps / Onboarding on a UCO. fields keys: next_steps, onboarding."""
    sf_fields = {_FIELD_MAP[k]: v for k, v in fields.items() if k in _FIELD_MAP}
    if not sf_fields:
        return {"updated": False, "reason": "nothing to update"}
    values = " ".join(f"{k}={json.dumps(v)}" for k, v in sf_fields.items())
    out = subprocess.run(
        ["sf", "data", "update", "record", "--target-org", _target_org(),
         "--sobject", "UseCase__c", "--record-id", uco_id, "--values", values, "--json"],
        capture_output=True, text=True,
    )
    txt = out.stdout
    i = txt.find("{")
    ok = i >= 0 and json.loads(txt[i:]).get("status") == 0
    if not ok:
        raise RuntimeError((out.stderr or out.stdout).strip()[:300] or "sf update failed")
    return {"updated": True, "fields": list(fields)}


def available() -> bool:
    try:
        _target_org()
        return True
    except Exception:
        return False
