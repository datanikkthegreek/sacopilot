"""Use-Case artifact generation — ports the use-cases skill's strict templates.

Generates Next Steps (Demand_Plan_Next_Steps__c) and Onboarding Plan
(Implementation_Notes__c) via Claude (Databricks gateway) from the current field
content + UCO context + the user's prompt. Honors stage gating (Onboarding U3+).
"""
from __future__ import annotations

from typing import Any

import anthropic

from sacopilot.backend import config

_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


NEXT_STEPS_TEMPLATE = """\
{DD/MM/YYYY today} – {SA abbreviation}
Status: {GREEN | AMBER | RED, default GREEN} – {explanation}
Achievement: {the major goal of this Use-Case}

Next Steps:
A {step} – {by DD/MM/YYYY or "done"} – {Owner: SA/PS/SSA/AE/DSA/STS}
B {step} – {date} – {Owner}
{continue C, D, E …}

Implementation Plan Agreed: {Yes | No, default Yes}
Onboarding Date Agreed: {Yes | No, default Yes}
Sponsorship Confirmed (Customer & Databricks): {Yes | No, default Yes}
Delivery Model: {default Self-Implemented}
Blockers / Risks: {None, or list A, B, C …}"""

ONBOARDING_TEMPLATE = """\
{DD/MM/YYYY today} – {SA abbreviation}
Objective: {objective of the Use-Case}
Exit Criteria: {when onboarding is complete}
Delivery Model: {PS | Self-Implemented | Partner, default Self-Implemented}

Milestones & Timeline (by):
A {step} – {by DD/MM/YYYY or "done"} – {Owner: SA/Customer/PS}
B {step} – {date} – {Owner}
{continue C, D, E …}

Risks & Mitigation:
A {risk}: {mitigation}
B {risk}: {mitigation}

Steering: {how the project is steered} ({name}/{role})"""

_RULES = """\
Authoring rules:
- Fill the template EXACTLY; add nothing not in the current content, the UCO
  context, or the user's instructions. Mark missing info `TBA`.
- Refresh the date to TODAY (Europe/Berlin), format DD/MM/YYYY.
- Preserve completed items from the current content; mark done items "done".
- Owner abbreviations only: SA, PS, SSA, AE, DSA, STS (multiple split with /).
- Output ONLY the filled artifact text — no preamble, no code fences."""

_STAGE_ORDER = {"U1": 1, "U2": 2, "U3": 3, "U4": 4, "U5": 5, "U6": 6}


def onboarding_allowed(stage: str | None) -> bool:
    return _STAGE_ORDER.get(stage or "", 0) >= 3


def generate(artifact: str, uco: dict, today: str, prompt: str = "") -> str:
    """artifact: 'next_steps' | 'onboarding'. uco: the get_uco() dict."""
    if artifact == "onboarding":
        if not onboarding_allowed(uco.get("stage")):
            raise RuntimeError(f"Onboarding Notes apply from stage U3 onward (this UCO is {uco.get('stage')}).")
        template, label, current = ONBOARDING_TEMPLATE, "Onboarding Plan", uco.get("onboarding", "")
    elif artifact == "next_steps":
        template, label, current = NEXT_STEPS_TEMPLATE, "Next Steps", uco.get("next_steps", "")
    else:
        raise ValueError(f"unknown artifact {artifact!r}")

    system = (
        f"You maintain the Databricks Field Engineering '{label}' artifact for a "
        f"Salesforce Use Case Object, using this STRICT template:\n\n{template}\n\n{_RULES}\n"
        f"Today is {today}.\n\n"
        "OUTPUT FORMAT: first the filled artifact text exactly per the template, "
        "then a line containing only `===FEEDBACK===`, then bullet-point feedback "
        "(like the CLI): every required item you marked TBA or had to assume, any "
        "dates earlier than today, and a one-line note of what you changed. If "
        "nothing is missing, write '- All required fields supplied.'"
    )
    ctx = (
        f"UCO: {uco.get('name')} | Account: {uco.get('account')} | Stage: {uco.get('stage')}\n"
        f"Description: {(uco.get('description') or '')[:2000]}\n"
        f"Owner: {uco.get('owner')} | Start: {uco.get('start_date')} | Go-live: {uco.get('go_live_date')}\n\n"
        f"CURRENT {label} (preserve history, refresh dates):\n{current or '(empty)'}\n\n"
        f"User instructions for this update:\n{prompt or '(none — refresh date and tidy, keep content)'}"
    )
    resp = _anthropic().messages.create(
        model=config.MODEL, max_tokens=2200, thinking={"type": "adaptive"},
        system=system, messages=[{"role": "user", "content": ctx}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    if "===FEEDBACK===" in raw:
        text, _, feedback = raw.partition("===FEEDBACK===")
        return {"text": text.strip(), "feedback": feedback.strip()}
    return {"text": raw, "feedback": ""}
