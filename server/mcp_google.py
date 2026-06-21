"""Bridge to the already-authenticated Google MCP server (dbexec).

The user's Google access (Calendar/Gmail/Drive/Docs) is provided by a
Databricks-managed MCP server — no app-side OAuth, no GCP project. We run one
persistent MCP client session on a dedicated background thread with its own
event loop, and expose a synchronous call_tool() the rest of the (sync) backend
can use.

This replaces the direct google-api-python-client OAuth path: the user may not
have rights to create a GCP OAuth client, but this server is already wired and
write-enabled (GOOGLE_MCP_WRITE_ENABLED).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from concurrent.futures import Future
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# How to launch the MCP server. Overridable, defaults to the dbexec single-server
# launcher used by Claude Code on this machine.
_COMMAND = os.environ.get("SACOPILOT_GOOGLE_MCP_CMD", "dbexec")
_ARGS = os.environ.get(
    "SACOPILOT_GOOGLE_MCP_ARGS", "repo run mcp start-single google"
).split()
_ENV = {
    **os.environ,
    "I_DANGEROUSLY_OPT_IN_TO_UNSUPPORTED_ALPHA_TOOLS": "true",
    "MCP_PRIVACY_SUMMARIZATION_ENABLED": "false",
}


class _McpBridge:
    """Owns a background thread + event loop running one long-lived MCP session.

    Generic over the server it launches (Google, Glean, …) — pass the command,
    args and a short name for error messages."""

    def __init__(self, command: str = _COMMAND, args: list[str] | None = None,
                 env: dict | None = None, name: str = "google") -> None:
        self._command = command
        self._args = args if args is not None else _ARGS
        self._env = env if env is not None else _ENV
        self._name = name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: ClientSession | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start_error: Exception | None = None
        self._lock = threading.Lock()

    def _run(self) -> None:
        async def main() -> None:
            params = StdioServerParameters(command=self._command, args=self._args, env=self._env)
            try:
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._session = session
                        self._ready.set()
                        # Keep the session alive until the loop is stopped.
                        self._stop = asyncio.Event()
                        await self._stop.wait()
            except Exception as e:  # noqa: BLE001
                self._start_error = e
                self._ready.set()

        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive() and self._session:
                return
            self._ready.clear()
            self._start_error = None
            self._thread = threading.Thread(target=self._run, daemon=True, name=f"mcp-{self._name}")
            self._thread.start()
        if not self._ready.wait(timeout=90):
            raise RuntimeError(f"{self._name} MCP server did not start within 90s")
        if self._start_error:
            raise RuntimeError(f"{self._name} MCP server failed to start: {self._start_error}")

    def call(self, tool: str, args: dict[str, Any], timeout: float = 120.0) -> Any:
        """Synchronously call an MCP tool; returns parsed JSON or raw text."""
        self._ensure_started()
        assert self._loop and self._session
        fut: Future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(tool, args), self._loop
        )
        result = fut.result(timeout=timeout)
        # MCP returns content blocks; the google server returns one JSON text block.
        text = ""
        for block in result.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        if result.isError:
            raise RuntimeError(f"MCP tool {tool} error: {text[:500]}")
        # The server may prepend diagnostic warnings (e.g. a failed privacy
        # summarization call) before the JSON payload; strip them so parsing
        # doesn't fall back to returning the raw string (which callers ignore).
        text = re.sub(r"^\s*\[WARNING:.*?\]\s*", "", text, flags=re.DOTALL)
        try:
            parsed = json.loads(text)
            # The google server wraps payloads as {"result": "<json string>"}.
            if isinstance(parsed, dict) and "result" in parsed and isinstance(parsed["result"], str):
                try:
                    return json.loads(parsed["result"])
                except json.JSONDecodeError:
                    return parsed["result"]
            return parsed
        except json.JSONDecodeError:
            return text

    def available(self) -> bool:
        try:
            self._ensure_started()
            return self._session is not None
        except Exception:
            return False


bridge = _McpBridge(_COMMAND, _ARGS, _ENV, name="google")


def call_tool(tool: str, args: dict[str, Any]) -> Any:
    return bridge.call(tool, args)


def is_available() -> bool:
    return bridge.available()
