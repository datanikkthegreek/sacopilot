"""Single source of truth for the email-classification taxonomy.

Facets map to nested Gmail labels (`Prefix/Value`). Gmail is the source of
truth for the labels themselves; this defines the controlled vocabulary the
classifier may assign. Keep in sync with the vault tag taxonomy.
"""
from __future__ import annotations

# Facet 1 — what kind of email
TYPE = ["Informative", "Action", "Waiting"]

# Facet 2 — the gate: which org. Decides whether DBX / Bosch / BU apply.
ORG = ["Customer", "Partner", "Internal"]

# Facet 3 — priority. P0=today/urgent, P1=this week, P2=FYI/whenever.
PRIO = ["0", "1", "2"]

# Facet 4 — Databricks-internal sub-type (only when Org=Internal)
DBX = ["Marketing", "Announcement", "Alerts", "Other", "People"]

# Facet 5 — Bosch sub-type (only when Org=Customer)
BOSCH = ["Operation", "Use-Case", "Commercial", "Escalation"]

# Facet 6 — Bosch business unit(s) (only when Org=Customer). Multiple allowed.
# Active vault BUs first, then the broader Bosch BU set, plus Account (cross-BU).
BU = [
    "PT", "HC", "PS", "MA", "DC", "BD", "BEG", "BMG", "BT", "M",
    "2WP", "EB", "EM", "ETAS", "ME", "MPS", "VM", "XC",
    "BCI", "BHCS", "HOME", "SO", "BSH", "CR", "GS",
    "Account",
]

# Label prefixes (nested Gmail label namespaces)
PREFIX = {
    "type": "Type",
    "org": "Org",
    "prio": "Prio",
    "dbx": "DBX",
    "bosch": "Bosch",
    "bu": "BU",
}
REVIEW_LABEL = "Needs/Review"


def all_label_names(facets: dict) -> list[str]:
    """Turn a classification dict into the flat list of Gmail label names."""
    labels: list[str] = []
    if facets.get("type"):
        labels.append(f"{PREFIX['type']}/{facets['type']}")
    if facets.get("org"):
        labels.append(f"{PREFIX['org']}/{facets['org']}")
    if facets.get("prio") is not None:
        labels.append(f"{PREFIX['prio']}/{facets['prio']}")
    if facets.get("dbx"):
        labels.append(f"{PREFIX['dbx']}/{facets['dbx']}")
    if facets.get("bosch"):
        labels.append(f"{PREFIX['bosch']}/{facets['bosch']}")
    for bu in facets.get("bu", []) or []:
        labels.append(f"{PREFIX['bu']}/{bu}")
    if facets.get("needs_review"):
        labels.append(REVIEW_LABEL)
    return labels


def every_possible_label() -> list[str]:
    """The full nested-label tree, for one-time gmail_ensure_labels creation."""
    labels = [REVIEW_LABEL]
    labels += [f"{PREFIX['type']}/{v}" for v in TYPE]
    labels += [f"{PREFIX['org']}/{v}" for v in ORG]
    labels += [f"{PREFIX['prio']}/{v}" for v in PRIO]
    labels += [f"{PREFIX['dbx']}/{v}" for v in DBX]
    labels += [f"{PREFIX['bosch']}/{v}" for v in BOSCH]
    labels += [f"{PREFIX['bu']}/{v}" for v in BU]
    return labels


def classification_schema() -> dict:
    """JSON schema for output_config.format — guarantees valid facet values."""
    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": TYPE},
            "org": {"type": "string", "enum": ORG},
            "prio": {"type": "string", "enum": PRIO},
            "dbx": {"type": ["string", "null"], "enum": DBX + [None]},
            "bosch": {"type": ["string", "null"], "enum": BOSCH + [None]},
            "bu": {"type": "array", "items": {"type": "string", "enum": BU}},
            "confidence": {"type": "number"},
            "rationale": {"type": "string"},
        },
        "required": ["type", "org", "prio", "dbx", "bosch", "bu", "confidence", "rationale"],
        "additionalProperties": False,
    }
