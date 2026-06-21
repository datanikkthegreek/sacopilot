"""Email classification via Claude structured output.

classify_email() returns the 6-facet set + confidence, schema-constrained so
the output is always valid. Org gates which conditional facets are meaningful:
Org=Internal -> dbx set, bosch/bu null/empty; Org=Customer -> bosch/bu set,
dbx null. Confidence below threshold flags Needs/Review.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from sacopilot.backend import config, taxonomy

_client: anthropic.Anthropic | None = None


def _anthropic() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _coerce(value, allowed: list, default=None):
    """Snap a model value to the allowed enum (case-insensitive); else default."""
    if value is None:
        return default
    for a in allowed:
        if str(value).strip().lower() == str(a).lower():
            return a
    return default


def _validate(facets: dict) -> dict:
    """Coerce a raw classification dict to valid taxonomy values."""
    facets["type"] = _coerce(facets.get("type"), taxonomy.TYPE, "Informative")
    facets["org"] = _coerce(facets.get("org"), taxonomy.ORG, "Internal")
    facets["prio"] = _coerce(facets.get("prio"), taxonomy.PRIO, "2")
    facets["dbx"] = _coerce(facets.get("dbx"), taxonomy.DBX)
    facets["bosch"] = _coerce(facets.get("bosch"), taxonomy.BOSCH)
    bu_raw = facets.get("bu") or []
    if isinstance(bu_raw, str):
        bu_raw = [bu_raw]
    facets["bu"] = [b for b in (_coerce(x, taxonomy.BU) for x in bu_raw) if b]
    try:
        facets["confidence"] = float(facets.get("confidence", 0))
    except (TypeError, ValueError):
        facets["confidence"] = 0.0
    return facets


# Compact account context so the classifier maps projects/topics to the right
# BU. Keep terse; this rides in the system prompt on every call.
ACCOUNT_CONTEXT = """Bosch BU reference (code: what it covers, key projects/keywords):
- PT (Power Tools): Marketing CDP / Composable CDP, shopping cart abandoner, Tealium, Braze, Commercetools, BW Migration, R3 data, DCL (Data Consolidation Layer), Data Hub, Sales Agent, Manufacturing AI, AOI. Contacts incl. Ivana Manojlovic, Alicja Sipowicz, Cagri Senol, Miladin Tajic.
- MA (Mobility Aftermarket): Thor platform, LOP/LOW logistics, Demand Forecasting.
- PS (Power Solutions): Nuernberg/Feuerbach/Budweis plants, ZeroBus, value creation.
- DC (Drive and Control / Rexroth): Platform Win, Synvert, ML use cases; lead Justus Schrage.
- BD (Bosch Digital): Redmesh, DPAI, Athena, SAP, central data platform.
- BMG, BT, M, BEG, HC: other Bosch BUs.
Marketing CDP / cart abandoner / Tealium / Braze / Commercetools => PT, NOT DC."""

SYSTEM = """You classify a Databricks Solutions Architect's email into a fixed label taxonomy.

The SA works the Bosch account. Apply this judgment:
- Org is the gate. Internal = from/about Databricks. Customer = Bosch (any Bosch domain/person). Partner = a third-party vendor (Braze, Kinaxis, Eviden, foryouandyourcustomers, Microsoft, etc.).
- Type: Action = needs the SA to do something. Waiting = SA is awaiting someone else's reply or has delegated. Informative = FYI, no action.
- Prio: 0 = urgent/today, 1 = this week, 2 = FYI/whenever.
- When Org=Internal: set dbx (Marketing/Announcement/Alerts/Other/People); leave bosch null and bu empty.
- When Org=Customer: set bosch (Operation/Use-Case/Commercial/Escalation) and bu (one or more Bosch business-unit codes; use Account when it's cross-BU/account-level); leave dbx null.
- When Org=Partner: leave dbx null, bosch null, bu empty unless a specific Bosch BU is clearly the subject.
- confidence in [0,1]: how sure you are overall. Be honest; low confidence is fine and triggers human review.
Return only the structured object."""


# Some endpoints (e.g. the Databricks AI Gateway) don't support
# output_config.format. We try structured output first, then fall back to a
# JSON-instructed prompt + client-side validation. Detected once, then cached.
_SUPPORTS_STRUCTURED: bool | None = None


def _extract_json(text: str) -> dict:
    """Parse a JSON object from model text, tolerating ```json fences/prose."""
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def classify_email(subject: str, sender: str, body: str,
                   examples: list[dict] | None = None) -> dict[str, Any]:
    """Classify one email. `examples` are prior user corrections (few-shot)."""
    global _SUPPORTS_STRUCTURED
    user_parts = []
    if examples:
        user_parts.append("Here are prior corrected classifications to learn the SA's judgment:")
        for ex in examples[-8:]:
            user_parts.append(json.dumps(ex, ensure_ascii=False))
        user_parts.append("---")
    user_parts.append(
        f"Classify this email:\nFrom: {sender}\nSubject: {subject}\n\n{body[:8000]}"
    )

    base_kwargs = dict(
        model=config.MODEL,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=SYSTEM + "\n\n" + ACCOUNT_CONTEXT,
    )

    def _call_structured():
        return _anthropic().messages.create(
            **base_kwargs,
            output_config={"format": {"type": "json_schema",
                                      "schema": taxonomy.classification_schema()}},
            messages=[{"role": "user", "content": "\n".join(user_parts)}],
        )

    def _call_json_prompt():
        schema_hint = (
            "Respond with ONLY a JSON object, no prose, with keys: "
            'type (one of ' + str(taxonomy.TYPE) + "), "
            "org (one of " + str(taxonomy.ORG) + "), "
            "prio (one of " + str(taxonomy.PRIO) + "), "
            "dbx (one of " + str(taxonomy.DBX) + " or null), "
            "bosch (one of " + str(taxonomy.BOSCH) + " or null), "
            "bu (array of " + str(taxonomy.BU) + "), "
            "confidence (number 0-1), rationale (string)."
        )
        return _anthropic().messages.create(
            **base_kwargs,
            messages=[{"role": "user", "content": "\n".join(user_parts) + "\n\n" + schema_hint}],
        )

    if _SUPPORTS_STRUCTURED is not False:
        try:
            resp = _call_structured()
            _SUPPORTS_STRUCTURED = True
        except anthropic.BadRequestError as e:
            if "output_config" in str(e):
                _SUPPORTS_STRUCTURED = False
                resp = _call_json_prompt()
            else:
                raise
    else:
        resp = _call_json_prompt()

    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    facets = _extract_json(text)
    facets = _validate(facets)
    # Normalize + apply the confidence gate.
    facets["needs_review"] = float(facets.get("confidence", 0)) < config.CONFIDENCE_THRESHOLD
    # Enforce the Org gate so stray conditional facets don't leak into labels.
    if facets.get("org") == "Internal":
        facets["bosch"], facets["bu"] = None, []
    elif facets.get("org") in ("Customer", "Partner"):
        facets["dbx"] = None
    facets["labels"] = taxonomy.all_label_names(facets)
    return facets
