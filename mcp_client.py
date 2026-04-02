# mcp_client.py
"""
Singleton MCP client for the policy-compliance-db server.

Uses a dedicated background thread with a persistent event loop so the
MCP stdio connection stays alive across multiple calls.

Usage:
    from mcp_client import mcp

    contacts = mcp.call("get_contacts", {"department": "HR"})
    task_id  = mcp.call("create_review_task", {"payload": {...}})["task_id"]
"""
import json
import asyncio
import threading
import logging
import atexit
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# The mcp_server package lives one level up from this project
MCP_SERVER_DIR = str(Path(__file__).resolve().parent.parent / "mcp_server")
# Parent of mcp_server so `python -m mcp_server.server` resolves correctly
MCP_SERVER_PARENT = str(Path(MCP_SERVER_DIR).parent)

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Sync wrapper around the MCP stdio client.

    Spawns a background thread with a persistent asyncio event loop.
    The MCP server subprocess and session live on that loop, so they
    survive across multiple .call() invocations.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: ClientSession | None = None
        self._cm = None
        self._session_cm = None
        self._connected = False
        self._lock = threading.Lock()

    # ── background loop ──────────────────────────────────────────

    def _start_loop(self):
        """Start a background thread running an asyncio event loop."""
        if self._loop is not None and self._loop.is_running():
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run(self, coro):
        """Schedule a coroutine on the background loop and wait for the result."""
        with self._lock:
            self._start_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    # ── connection ───────────────────────────────────────────────

    async def _connect(self):
        if self._connected:
            return

        server_params = StdioServerParameters(
            command="python",
            args=["server.py"],
            cwd=MCP_SERVER_DIR,
        )
        self._cm = stdio_client(server_params)
        self._read, self._write = await self._cm.__aenter__()
        self._session_cm = ClientSession(self._read, self._write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        self._connected = True
        logger.info("MCP client connected to policy-compliance-db server")

    # ── public API ───────────────────────────────────────────────

    def call(self, tool_name: str, arguments: dict = None):
        """Call an MCP tool synchronously. Safe from any thread / event-loop state."""
        return self._run(self._call_async(tool_name, arguments))

    async def _call_async(self, tool_name: str, arguments: dict = None):
        await self._connect()
        result = await self._session.call_tool(tool_name, arguments or {})
        if result.content and len(result.content) > 0:
            return json.loads(result.content[0].text)
        return None

    def list_tools(self) -> list:
        """List all available tools on the server."""
        return self._run(self._list_tools_async())

    async def _list_tools_async(self) -> list:
        await self._connect()
        result = await self._session.list_tools()
        return result.tools

    def close(self):
        """Shut down the background loop. The daemon thread and server subprocess
        will be cleaned up automatically on process exit."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._connected = False


# Singleton instance — import this
mcp = MCPClient()
atexit.register(mcp.close)
