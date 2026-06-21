"""Unit tests for the cache-backed classifier — no network/creds.

Monkeypatches the classifier's Lakebase calls so we exercise orchestration
only: the subject+sender+snippet rule and the save call shape.
"""
from __future__ import annotations

from sacopilot.backend import classifier, taxonomy
from sacopilot.backend.tools import classify as _classify


def test_classify_thread_uses_snippet_only_and_saves(monkeypatch):
    captured = {}

    def fake_classify(subject, sender, body, examples=None):
        captured["args"] = (subject, sender, body)
        return {
            "type": "Action", "org": "Customer", "prio": "1", "dbx": None,
            "bosch": "Use-Case", "bu": ["PT"], "confidence": 0.9,
            "rationale": "r", "needs_review": False,
            "labels": taxonomy.all_label_names(
                {"type": "Action", "org": "Customer", "prio": "1",
                 "bosch": "Use-Case", "bu": ["PT"]}),
        }

    saved = {}

    def fake_save(thread_id, facets, labels):
        saved.update(thread_id=thread_id, labels=labels)
        return {"saved": True}

    monkeypatch.setattr(_classify, "classify_email", fake_classify)
    monkeypatch.setattr(classifier.lakebase, "save_classification", fake_save)

    thread = {"thread_id": "t1", "subject": "CDP cart", "from": "ivana@bosch.com",
              "snippet": "short snippet text"}
    res = classifier.classify_thread(thread, examples=[{"subject": "ex"}])

    # Body passed to the classifier MUST be the snippet, never a full body.
    assert captured["args"] == ("CDP cart", "ivana@bosch.com", "short snippet text")
    assert saved["thread_id"] == "t1"
    assert "BU/PT" in res["labels"] and res["needs_review"] is False


def test_label_regeneration_from_facets():
    facets = {"type": "Informative", "org": "Internal", "prio": "2",
              "dbx": "Alerts", "bosch": None, "bu": []}
    labels = taxonomy.all_label_names(facets)
    assert labels == ["Type/Informative", "Org/Internal", "Prio/2", "DBX/Alerts"]
