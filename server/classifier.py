"""Batch conversation-classification service (decoupled from the chat agent).

Operates over the Lakebase inbox cache (populated by server/sync.py): it picks
cached inbox threads that aren't classified yet, classifies each, and writes the
classification onto the cached thread row. No approval gate — results apply
immediately and the user corrects them inline.

HARD RULE: classify from subject + sender + snippet ONLY (already in the cache).
Full message bodies are never fetched for classification.
"""
from __future__ import annotations

from typing import Any

from server import lakebase
from server.tools import classify as _classify


def unclassified_threads(limit: int = 500) -> list[dict[str, Any]]:
    """Cached inbox conversations not yet classified."""
    return lakebase.unclassified_inbox_threads(limit)


def classify_thread(thread: dict, examples: list[dict] | None = None) -> dict[str, Any]:
    """Classify one cached conversation (subject+sender+snippet) and save it."""
    subject = thread.get("subject") or "(no subject)"
    sender = thread.get("from") or ""
    snippet = thread.get("snippet") or ""
    facets = _classify.classify_email(subject, sender, snippet, examples=examples)
    lakebase.save_classification(thread["thread_id"], facets, facets["labels"])
    return {
        "thread_id": thread["thread_id"],
        "labels": facets["labels"],
        "facets": facets,
        "needs_review": facets.get("needs_review", False),
    }


def few_shot_examples(limit: int = 8) -> list[dict]:
    """Few-shot examples = the user's recent manual corrections (from Lakebase)."""
    try:
        return lakebase.recent_adjusted(limit)
    except Exception:
        return []
