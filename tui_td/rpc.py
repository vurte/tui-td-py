"""JSON-RPC 2.0 client for tui-td MCP server over stdio.

Manages the subprocess lifecycle, MCP handshake, and request/response cycle.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import signal
from typing import Any

from .exceptions import TUIConnectionError, TUIDriverError

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "tui-td-py"
CLIENT_VERSION = "0.1.0"


class RpcClient:
    """Low-level JSON-RPC 2.0 client for the tui-td MCP server.

    Manages a subprocess running ``tui-td serve`` and sends/receives
    JSON-RPC messages over stdin/stdout.

    Usage::

        client = RpcClient("htop", rows=40, cols=120)
        await client.connect()
        result = await client.call("tui_state", format="ai")
        await client.close()
    """

    def __init__(
        self,
        command: str,
        *,
        rows: int = 40,
        cols: int = 120,
        timeout: float = 30.0,
        executable: str = "tui-td",
    ) -> None:
        self._tui_command = command
        self._rows = rows
        self._cols = cols
        self._timeout = timeout
        self._executable = executable

        self._process: asyncio.subprocess.Process | None = None
        self._request_id: int = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._connected: bool = False

    async def connect(self) -> None:
        """Start the tui-td MCP server and perform the handshake.

        Raises:
            TUIConnectionError: If the subprocess fails to start or the
                MCP handshake fails.
        """
        if self._connected:
            raise TUIDriverError("Already connected. Call close() first.")

        # Start subprocess
        try:
            self._process = await asyncio.create_subprocess_exec(
                self._executable,
                "serve",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise TUIConnectionError(
                f"tui-td executable not found: {self._executable}. "
                "Install it with: gem install tui-td"
            ) from exc
        except OSError as exc:
            raise TUIConnectionError(f"Failed to start tui-td: {exc}") from exc

        # Start reader loop
        self._reader_task = asyncio.create_task(self._read_loop())

        # MCP handshake: initialize
        init_result = await self._send_request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": CLIENT_NAME,
                    "version": CLIENT_VERSION,
                },
            },
        )

        server_info = init_result.get("serverInfo", {})
        logger.info(
            "Connected to %s v%s (protocol %s)",
            server_info.get("name", "unknown"),
            server_info.get("version", "unknown"),
            init_result.get("protocolVersion", "unknown"),
        )

        # Send initialized notification (MCP spec)
        await self._send_notification("notifications/initialized")

        self._connected = True

    async def call(self, tool_name: str, **arguments: Any) -> str:
        """Call a tui-td MCP tool and return its text result.

        Args:
            tool_name: The MCP tool name (e.g. ``"tui_start"``).
            **arguments: Tool-specific arguments.

        Returns:
            The text content of the tool's response.

        Raises:
            TUIDriverError: If not connected.
            TUIConnectionError: If the call fails or returns an error.
        """
        if not self._connected:
            raise TUIDriverError("Not connected. Call connect() first.")

        result = await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )

        content = result.get("content", [])
        text_parts: list[str] = []
        is_error = result.get("isError", False)

        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))

        text = "\n".join(text_parts)

        if is_error:
            raise TUIConnectionError(f"Tool '{tool_name}' returned error: {text}")

        return text

    async def close(self) -> None:
        """Close the MCP connection and terminate the subprocess."""
        if not self._connected:
            return

        # Cancel reader task
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
        self._reader_task = None

        # Terminate process
        if self._process and self._process.returncode is None:
            try:
                self._process.send_signal(signal.SIGTERM)
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass

        self._process = None
        self._connected = False
        self._pending.clear()
        logger.debug("RpcClient closed.")

    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response."""
        self._request_id += 1
        req_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        await self._write_message(request)

        try:
            return await asyncio.wait_for(future, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TUIConnectionError(
                f"Request '{method}' timed out after {self._timeout:.1f}s"
            ) from None

    async def _send_notification(self, method: str) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        await self._write_message(notification)

    async def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the subprocess stdin."""
        if self._process is None or self._process.stdin is None:
            raise TUIConnectionError("Subprocess is not running.")
        line = json.dumps(message, ensure_ascii=False) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()
        logger.debug("Sent: %s", message.get("method", "notification"))

    async def _read_loop(self) -> None:
        """Continuously read JSON-RPC responses from stdout."""
        if self._process is None or self._process.stdout is None:
            return

        # Increase the readline buffer limit to handle large JSON
        # responses (e.g., full state grid: 80×40 = 3200 cells → ~300KB).
        self._process.stdout._limit = 10 * 1024 * 1024  # 10 MB

        while True:
            try:
                line = await self._process.stdout.readline()
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                logger.debug("Stdout read error: %s", exc)
                break

            if not line:
                logger.debug("Subprocess stdout closed (EOF)")
                break

            self._process_line(line)

    def _process_line(self, line: bytes) -> None:
        """Parse a single JSON-RPC line and resolve the pending future."""
        line_str = line.strip().decode("utf-8", errors="replace")
        if not line_str:
            return

        try:
            message = json.loads(line_str)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON-RPC response: %s", exc)
            return

        # Ignore responses without id (notifications)
        msg_id = message.get("id")
        if msg_id is None:
            return

        future = self._pending.pop(msg_id, None)
        if future is None:
            logger.debug("Received response for unknown id: %s", msg_id)
            return

        if "error" in message:
            err = message["error"]
            future.set_exception(
                TUIConnectionError(
                    f"JSON-RPC error {err.get('code', '?')}: {err.get('message', 'Unknown')}"
                )
            )
        else:
            future.set_result(message.get("result", {}))
