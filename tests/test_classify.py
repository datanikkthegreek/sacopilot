"""Regression test for the email classifier against a fixture set.

Guards against taxonomy drift. Asserts only the facets each fixture pins
(partial match) so the model has latitude on unspecified facets.

Skips automatically if no Anthropic key is configured (CI without creds).
Run: uv run pytest tests/test_classify.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from server import config
from server.tools import classify

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "emails.json").read_text())

pytestmark = pytest.mark.skipif(
    not config.has_anthropic_key(), reason="no Anthropic key configured"
)


@pytest.mark.parametrize("fx", FIXTURES, ids=[f["name"] for f in FIXTURES])
def test_classification(fx):
    result = classify.classify_email(fx["subject"], fx["from"], fx["body"])
    exp = fx["expect"]

    if "org" in exp:
        assert result["org"] == exp["org"], f"org: {result}"
    if "type" in exp:
        assert result["type"] == exp["type"], f"type: {result}"
    if "dbx" in exp:
        assert result["dbx"] == exp["dbx"], f"dbx: {result}"
    if "bosch" in exp:
        assert result["bosch"] == exp["bosch"], f"bosch: {result}"
    if "bu_includes" in exp:
        assert exp["bu_includes"] in (result.get("bu") or []), f"bu: {result}"
    if "prio_max" in exp:
        assert result["prio"] <= exp["prio_max"], f"prio: {result}"  # "0"<"1"<"2"
