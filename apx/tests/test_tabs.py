"""Unit tests for the Meetings + Use-Cases backend logic (no network)."""
from __future__ import annotations

import datetime as _dt

from sacopilot.backend import salesforce, usecase_gen
from sacopilot.backend.routes import meetings


def test_week_bounds_snaps_to_monday_friday():
    # 2026-06-17 is a Wednesday → Mon 2026-06-15 .. Sat 2026-06-20.
    lo, hi, monday = meetings._week_bounds("2026-06-17")
    assert monday == "2026-06-15"
    assert lo.weekday() == 0  # Monday
    assert (hi - lo) == _dt.timedelta(days=5)


def test_soql_escapes_quotes():
    assert salesforce._esc("O'Brien") == "O\\'Brien"


def test_onboarding_stage_gating():
    assert usecase_gen.onboarding_allowed("U3") is True
    assert usecase_gen.onboarding_allowed("U5") is True
    assert usecase_gen.onboarding_allowed("U2") is False
    assert usecase_gen.onboarding_allowed(None) is False


def test_unknown_artifact_rejected():
    import pytest
    with pytest.raises(ValueError):
        usecase_gen.generate("bogus", {"stage": "U3"}, "01/01/2026", "")


def test_usecase_quality_scoring():
    import datetime as dt
    from sacopilot.backend import usecase_quality as q
    today = dt.date(2026, 6, 21)
    # Full score: both artifacts dated today, strategy + status present.
    full = q.compute("21/06/2026 - NS\n...", "20/06/2026 - NS\n...", "PS", "Green", today)
    assert full["score"] == 6 and full["missing"] == []
    # Empty onboarding -> allowed, no penalty (both onboarding rules pass).
    part = q.compute("21/06/2026 - NS", "", "PS", "Green", today)
    assert part["score"] == 6 and part["missing"] == []
    # #keytechwin-only onboarding -> also allowed (singular or plural).
    for t in ("#keytechwin", "  #KeyTechWins "):
        tag = q.compute("21/06/2026 - NS", t, "PS", "Green", today)
        assert tag["score"] == 6 and tag["missing"] == [], t
    # Malformed onboarding date (real content) -> rule2 + rule4 fail; no
    # strategy/status -> rules 5/6 fail; only rule1 (valid old NS date) passes.
    bad = q.compute("01/01/2020 - NS", "no date here", None, None, today)
    assert bad["score"] == 1
