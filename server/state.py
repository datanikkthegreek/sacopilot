"""Local app state: email classification index + user corrections.

email-state.json mirrors the .sync-state.json philosophy — a per-message index
so re-runs never reclassify, plus a watermark. corrections.json stores user
re-labels as few-shot examples for the classifier learning loop.
Both are local JSON, git-ignored.
"""
from __future__ import annotations

import json
from typing import Any

from server import config


def _load(path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save(path, data: dict) -> None:
    config.ensure_app_home()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# --- Email classification index ---------------------------------------------

def load_email_state() -> dict:
    state = _load(config.EMAIL_STATE_PATH)
    state.setdefault("watermark", None)   # ISO date for `after:` queries
    state.setdefault("classified", {})    # message_id -> facets dict
    return state


def record_classification(message_id: str, facets: dict) -> None:
    state = load_email_state()
    state["classified"][message_id] = facets
    _save(config.EMAIL_STATE_PATH, state)


def set_watermark(iso_date: str) -> None:
    state = load_email_state()
    state["watermark"] = iso_date
    _save(config.EMAIL_STATE_PATH, state)


def is_classified(message_id: str) -> bool:
    return message_id in load_email_state()["classified"]


# --- Corrections (learning loop) ---------------------------------------------

def load_corrections() -> list[dict]:
    data = _load(config.CORRECTIONS_PATH)
    return data.get("examples", [])


def add_correction(subject: str, sender: str, corrected_facets: dict) -> None:
    """Store a user-corrected classification as a few-shot example."""
    data = _load(config.CORRECTIONS_PATH)
    examples = data.get("examples", [])
    examples.append({
        "subject": subject,
        "from": sender,
        "type": corrected_facets.get("type"),
        "org": corrected_facets.get("org"),
        "prio": corrected_facets.get("prio"),
        "dbx": corrected_facets.get("dbx"),
        "bosch": corrected_facets.get("bosch"),
        "bu": corrected_facets.get("bu", []),
    })
    data["examples"] = examples[-100:]  # cap
    _save(config.CORRECTIONS_PATH, data)
