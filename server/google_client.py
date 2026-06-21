"""DEPRECATED — Google now goes through the dbexec MCP server.

The app no longer uses a direct OAuth client. Google access (Calendar/Gmail/
Drive/Docs) is provided by the already-authenticated Databricks-managed MCP
server; see server/mcp_google.py and server/tools/google.py.

Kept only so the old `python -m server.google_client auth` command prints a
clear pointer instead of a stack trace.
"""
from __future__ import annotations

import sys

from server import mcp_google

_NOTICE = (
    "SA Copilot no longer uses a direct Google OAuth client.\n"
    "Google is reached via the dbexec MCP server (already authenticated).\n"
    "Nothing to set up. Check connectivity with:\n"
    "    uv run python -c \"from server import mcp_google; print(mcp_google.is_available())\""
)


def is_authorized() -> bool:
    return mcp_google.is_available()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        print(_NOTICE)
    else:
        print("available" if mcp_google.is_available() else "unavailable")
