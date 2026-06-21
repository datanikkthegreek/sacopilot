"""Auto-categorise calendar meetings into the user's Google categories.

Classifies UNCOLOURED events into one of five categories and returns the
mapping to Google colorIds. External attendees are detected by inversion (any
non-databricks.com domain), so all Bosch sub-domains are covered automatically.
Already-coloured events are used as few-shot examples (their colour = the user's
category) so the model matches the user's judgment.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from sacopilot.backend import config

# Category <-> Google event colorId.
CAT_TO_COLOR = {
    "Customer External": "6",   # Tangerine
    "Customer Internal": "9",   # Blueberry
    "Databricks Internal": "10",  # Basil
    "Preps": "3",               # Grape
    "Private": "5",             # Banana
}
COLOR_TO_CAT = {v: k for k, v in CAT_TO_COLOR.items()}
CATEGORIES = list(CAT_TO_COLOR)

INTERNAL_DOMAINS = {"databricks.com"}
# Known Bosch domains — hints for the model, NOT a gate (external = non-databricks).
BOSCH_HINTS = ["bosch.com", "de.bosch.com", "bshg.com", "boschrexroth.com", "boschrexroth.de"]

_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _domain(email: str | None) -> str:
    return (email or "").split("@")[-1].lower() if email and "@" in email else ""


def has_external(attendees: list[dict]) -> bool:
    """True if any attendee is outside Databricks (i.e. a customer/external)."""
    for a in attendees or []:
        d = _domain(a.get("email"))
        if d and d not in INTERNAL_DOMAINS:
            return True
    return False


def _domains(attendees: list[dict]) -> str:
    ds = sorted({_domain(a.get("email")) for a in attendees or [] if _domain(a.get("email"))})
    return ", ".join(ds) or "(none)"


SYSTEM = f"""You categorise a Databricks Solutions Architect's calendar events into EXACTLY one of:
- Customer External: external (customer) attendees are present / customer-facing meeting.
- Customer Internal: only Databricks attendees, but the meeting is ABOUT a customer.
- Databricks Internal: internal Databricks team / enablement / ops, no customer focus.
- Preps: preparation or focus-work blocks (often solo, no guests).
- Private: personal (lunch, gym, travel, family, errands, appointments).

Rules:
- An attendee is EXTERNAL if their email domain is not databricks.com. ANY external attendee => Customer External.
  (The customer is Bosch; its domains include {", ".join(BOSCH_HINTS)} and others — but the rule is simply: non-databricks domain = external.)
- No external attendees => choose among Customer Internal / Databricks Internal / Preps / Private from the title + context.
- Output ONLY a JSON array of objects {{"i": <index>, "category": "<one of the five>"}} — one per input event, no prose."""


def classify(uncoloured: list[dict], examples: list[dict]) -> dict[str, str]:
    """Return {event_id: category} for the uncoloured events. Index-based output
    (compact, robust) is mapped back to event ids here."""
    if not uncoloured:
        return {}
    ex_lines = []
    for e in examples[:40]:
        ex_lines.append(f'- "{e["summary"]}" [domains: {_domains(e.get("attendees", []))}] -> {e["category"]}')
    items = [{
        "i": i,
        "summary": e.get("summary", ""),
        "domains": _domains(e.get("attendees", [])),
        "has_external": has_external(e.get("attendees", [])),
        "snippet": (e.get("description") or "")[:160],
    } for i, e in enumerate(uncoloured)]
    user = ""
    if ex_lines:
        user += "Examples of how I already categorise (title -> category):\n" + "\n".join(ex_lines) + "\n\n"
    user += ('Categorise these events. Return a JSON array of {"i": <index>, "category": <one of the five>}:\n'
             + json.dumps(items, ensure_ascii=False))

    resp = _anthropic().messages.create(
        model=config.MODEL, max_tokens=4000,
        system=SYSTEM, messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        return {}
    try:
        arr = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    for o in arr:
        if not isinstance(o, dict):
            continue
        idx, cat = o.get("i"), o.get("category")
        if isinstance(idx, int) and 0 <= idx < len(uncoloured) and cat in CAT_TO_COLOR:
            out[uncoloured[idx]["id"]] = cat
    return out
