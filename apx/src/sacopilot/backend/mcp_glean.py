"""Bridge to the Glean MCP server (dbexec), reusing the generic MCP bridge.

Glean is an important context source for drafting replies. Like Google, it's
reached through the OAuth-backed dbexec MCP (no API token — not permitted here).
All access is best-effort: if Glean is unavailable, reply drafting degrades
gracefully (no Glean context) rather than failing.
"""
from __future__ import annotations

import os
import re
from typing import Any

from sacopilot.backend.mcp_google import _ENV, _McpBridge

_COMMAND = os.environ.get("SACOPILOT_GLEAN_MCP_CMD", "dbexec")
_ARGS = os.environ.get(
    "SACOPILOT_GLEAN_MCP_ARGS", "repo run mcp start-single glean"
).split()

bridge = _McpBridge(_COMMAND, _ARGS, _ENV, name="glean")


def is_available() -> bool:
    return bridge.available()


def _parse_markdown(text: str) -> list[dict[str, str]]:
    """The Glean MCP `search` tool returns markdown, not JSON. Parse the blocks:
    `**N. <title>**` / `**URL:** ...` / `**Snippet:** ...`."""
    out: list[dict[str, str]] = []
    for block in re.split(r"\n(?=\*\*\d+\.\s)", text):
        m = re.search(r"\*\*\d+\.\s*(.+?)\*\*", block)
        if not m:
            continue
        title = m.group(1).strip()
        url = (re.search(r"\*\*URL:\*\*\s*(\S.*)", block) or [None, ""])[1].strip()
        snip = (re.search(r"\*\*Snippet:\*\*\s*(.+)", block, re.S) or [None, ""])[1].strip()
        if snip.lower().startswith("no snippet"):
            snip = ""
        if title.lower() == "no title" and not url:
            continue  # empty placeholder result
        out.append({"title": title, "url": url, "snippet": snip[:400]})
    return out


def search(query: str, page_size: int = 5) -> list[dict[str, Any]]:
    """Search Glean; return a compact list of {title, url, snippet}. Best-effort."""
    try:
        res = bridge.call("search", {"query": query, "page_size": page_size}, timeout=60)
    except Exception:
        return []
    if isinstance(res, str):
        return _parse_markdown(res)[:page_size]
    # Fallback if a future server returns JSON.
    results = res.get("results", res.get("documents", [])) if isinstance(res, dict) else []
    out = []
    for r in results[:page_size]:
        if not isinstance(r, dict):
            continue
        doc = r.get("document", r)
        out.append({
            "title": doc.get("title") or r.get("title") or "Glean result",
            "url": doc.get("url") or r.get("url") or "",
            "snippet": str(r.get("snippet") or "")[:400],
        })
    return out
