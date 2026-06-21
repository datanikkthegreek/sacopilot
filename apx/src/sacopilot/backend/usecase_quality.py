"""Use-Case quality score (0–6) + the update dates parsed from the artifacts.

The "update date" of Next Steps / Onboarding Notes is the DD/MM/YYYY on the
first line of the artifact (the template's date stamp). Six rules, 1 point each:

  1  Next Steps date is NULL or a valid DD/MM/YYYY string
  2  Onboarding date is NULL or a valid DD/MM/YYYY string
  3  Next Steps updated within the last 8 days
  4  Onboarding updated within the last 8 days
  5  Implementation strategy set
  6  Implementation status set
"""
from __future__ import annotations

import datetime as _dt
import re

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def parse_update_date(text: str | None) -> tuple[_dt.date | None, bool]:
    """Return (date, valid). date = DD/MM/YYYY on the first line, or None.
    valid = True when the artifact is empty (NULL) OR the first line is a valid
    DD/MM/YYYY; False when there is content but no valid leading date."""
    if not text or not text.strip():
        return None, True  # NULL counts as "clean" per rules 1/2
    first = text.strip().splitlines()[0]
    m = _DATE_RE.search(first)
    if not m:
        return None, False
    d, mo, y = (int(x) for x in m.groups())
    try:
        return _dt.date(y, mo, d), True
    except ValueError:
        return None, False


def _recent(date: _dt.date | None, today: _dt.date, days: int = 8) -> bool:
    return date is not None and date >= today - _dt.timedelta(days=days)


def onboarding_blank(text: str | None) -> bool:
    """Onboarding Notes count as 'allowed/blank' (no quality penalty) when they
    are empty or contain only the #keytechwins tag."""
    if not text or not text.strip():
        return True
    cleaned = re.sub(r"#?keytechwins", "", text, flags=re.IGNORECASE).strip()
    return cleaned == ""


def compute(ns_text: str | None, ob_text: str | None,
            strategy: str | None, status: str | None,
            today: _dt.date | None = None) -> dict:
    today = today or _dt.date.today()
    ns_date, ns_ok = parse_update_date(ns_text)
    ob_date, ob_ok = parse_update_date(ob_text)
    # Empty / #keytechwins-only Onboarding Notes are allowed — no penalty.
    ob_allowed = onboarding_blank(ob_text)
    rules = [
        ("Next Steps date is a valid DD/MM/YYYY", ns_ok),
        ("Onboarding date is a valid DD/MM/YYYY", ob_ok or ob_allowed),
        ("Next Steps updated within the last 8 days", _recent(ns_date, today)),
        ("Onboarding updated within the last 8 days", _recent(ob_date, today) or ob_allowed),
        ("Implementation strategy is set", bool(strategy and str(strategy).strip())),
        ("Implementation status is set", bool(status and str(status).strip())),
    ]
    return {
        "score": sum(1 for _, ok in rules if ok),
        "missing": [label for label, ok in rules if not ok],
        "ns_update_date": ns_date.strftime("%d/%m/%Y") if ns_date else None,
        "ob_update_date": ob_date.strftime("%d/%m/%Y") if ob_date else None,
    }
