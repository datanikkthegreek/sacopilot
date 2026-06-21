"""Backend smoke tests — no network/creds required.

Guards the wiring: app imports, all routes mount, the tool registry is
consistent, every effecting tool is gated, and read tools gate cleanly when
Google is unauthorized.
"""
from __future__ import annotations

from server import approval
from server.tools import registry


def test_app_imports_and_routes_mount():
    import app
    paths = {r.path for r in app.app.routes if hasattr(r, "path")}
    for expected in [
        "/health",
        "/api/agent/message", "/api/agent/approve", "/api/agent/pending",
        "/api/mail/threads", "/api/mail/thread/{thread_id}", "/api/mail/sync",
        "/api/mail/taxonomy", "/api/mail/classify",
        "/api/mail/classify/{thread_id}", "/api/mail/status/{thread_id}",
        "/api/mail/reply/{thread_id}", "/api/meetings/today",
    ]:
        assert expected in paths, f"missing route {expected}"


def test_registry_consistent():
    tool_names = {t["name"] for t in registry.TOOLS}
    dispatch_names = set(registry.DISPATCH)
    assert tool_names == dispatch_names, (
        f"schema/dispatch mismatch: {tool_names ^ dispatch_names}"
    )


def test_effecting_tools_are_registered_and_gated():
    for name in approval.EFFECTING_TOOLS:
        # commit_writes/gmail_* must exist in dispatch and be flagged effecting
        assert name in registry.DISPATCH, f"{name} not in dispatch"
        assert approval.manager.is_effecting(name)
    # a clearly-read tool must not be gated
    assert not approval.manager.is_effecting("vault_search")
    assert not approval.manager.is_effecting("gmail_get_message")


def test_read_tools_gate_without_google():
    from server import mcp_google
    from server.tools import google
    import pytest
    # Only meaningful when the dbexec MCP is NOT reachable; skip if it is live.
    if mcp_google.is_available():
        pytest.skip("dbexec Google MCP is available in this environment")
    with pytest.raises(RuntimeError):
        google.calendar_list()
