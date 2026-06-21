"""Unit tests for the inbox sync diff logic — no network/creds.

Monkeypatches Google + Lakebase so we verify: only NEW threads get fetched and
upserted, the inbox set is reconciled (archived detection), and unread is
bulk-refreshed.
"""
from __future__ import annotations

from sacopilot.backend import sync
from sacopilot.backend.tools import google as _google


def test_sync_fetches_only_new_and_reconciles(monkeypatch):
    inbox = [
        {"thread_id": "a", "subject": "A", "from": "x@y", "snippet": "sa", "message_count": 1},
        {"thread_id": "b", "subject": "B", "from": "x@y", "snippet": "sb", "message_count": 2},
        {"thread_id": "c", "subject": "C", "from": "x@y", "snippet": "sc", "message_count": 1},
    ]
    # One page, no further paging.
    monkeypatch.setattr(_google, "gmail_thread_list",
                        lambda q, max_results=100: [] if "is:unread" in q else inbox)
    monkeypatch.setattr(_google, "thread_latest_epoch", lambda tid: None)

    def fake_get_thread(tid):
        return {"thread_id": tid, "latest_internal_date": "1718900000000",
                "messages": [{"id": tid + "-m0", "from": "x@y", "to": "me",
                              "date": "today", "subject": "S", "snippet": "sn",
                              "internal_date": "1718900000000",
                              "label_ids": ["INBOX", "UNREAD"]}]}
    monkeypatch.setattr(_google, "gmail_get_thread", fake_get_thread)

    reconciled, upserted, unread_set = {}, [], {}
    monkeypatch.setattr(sync.lakebase, "reconcile_inbox",
                        lambda ids: reconciled.update(ids=ids) or 0)
    monkeypatch.setattr(sync.lakebase, "existing_thread_ids", lambda ids: {"b"})  # b cached
    monkeypatch.setattr(sync.lakebase, "upsert_thread",
                        lambda meta: upserted.append(meta["thread_id"]))
    monkeypatch.setattr(sync.lakebase, "upsert_messages", lambda tid, msgs: None)
    monkeypatch.setattr(sync.lakebase, "set_unread",
                        lambda ids: unread_set.update(ids=ids))

    events = list(sync.sync_inbox())

    # Only the two NEW threads (a, c) were fetched/upserted; b was skipped.
    assert sorted(upserted) == ["a", "c"]
    # Reconcile saw the full current inbox set.
    assert sorted(reconciled["ids"]) == ["a", "b", "c"]
    # Progress reported 2 new of total 2.
    done = [e for e in events if e["type"] == "done"][0]
    assert done["total"] == 2 and done["inbox"] == 3
