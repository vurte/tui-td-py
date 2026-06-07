"""Tests for the JSON-RPC 2.0 client."""

from __future__ import annotations

import asyncio
import json

import pytest

from tui_td.exceptions import TUIConnectionError, TUIDriverError
from tui_td.rpc import RpcClient


class FakeProcess:
    """Simulates a tui-td subprocess for testing."""

    def __init__(self, responses: list[dict | None] | None = None) -> None:
        self.responses = responses or []
        self._response_index = 0
        self.returncode: int | None = None
        self.stdin_data: list[str] = []
        self._stdout_queue: asyncio.Queue[bytes] = asyncio.Queue()

    @property
    def stdout(self) -> FakeStreamReader:
        return FakeStreamReader(self._stdout_queue)

    @property
    def stdin(self) -> FakeStreamWriter:
        return FakeStreamWriter(self.stdin_data, self)

    async def wait(self) -> None:
        pass

    def send_signal(self, sig: int) -> None:
        self.returncode = -1

    def kill(self) -> None:
        self.returncode = -9

    def enqueue_response(self, response: dict) -> None:
        self._stdout_queue.put_nowait((json.dumps(response) + "\n").encode("utf-8"))


class FakeStreamReader:
    def __init__(self, queue: asyncio.Queue[bytes]) -> None:
        self._queue = queue
        self._limit = 10 * 1024 * 1024  # Match RpcClient limit

    async def readline(self) -> bytes:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return b""


class FakeStreamWriter:
    def __init__(self, data: list[str], process: FakeProcess) -> None:
        self.data = data
        self.process = process

    def write(self, data: bytes) -> None:
        self.data.append(data.decode("utf-8"))

    async def drain(self) -> None:
        pass


@pytest.fixture
def fake_process_factory():
    """Returns a factory that creates FakeProcess instances for patching."""
    created: list[FakeProcess] = []

    async def factory(*args, **kwargs):
        proc = FakeProcess()
        created.append(proc)
        return proc

    yield factory, created


class TestRpcClientConnect:
    """Tests for RpcClient.connect()."""

    @pytest.mark.asyncio
    async def test_connect_exchanges_messages(self, monkeypatch):
        """Connect should send initialize, receive response, send initialized notification."""
        proc = FakeProcess()

        # Enqueue the initialize response
        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tui-td", "version": "0.2.20"},
                },
            }
        )

        async def fake_subprocess(*args, **kwargs):
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

        client = RpcClient("echo test")
        await client.connect()
        await client.close()

        # Check that initialize was sent
        sent_lines = [json.loads(line) for line in proc.stdin_data]
        assert len(sent_lines) == 2

        # First message: initialize
        assert sent_lines[0]["method"] == "initialize"
        assert sent_lines[0]["id"] == 1
        assert sent_lines[0]["params"]["protocolVersion"] == "2024-11-05"

        # Second message: notifications/initialized
        assert sent_lines[1]["method"] == "notifications/initialized"
        assert "id" not in sent_lines[1]

    @pytest.mark.asyncio
    async def test_connect_handles_executable_not_found(self, monkeypatch):
        """Connect should raise TUIConnectionError if tui-td is not installed."""

        async def fake_subprocess(*args, **kwargs):
            raise FileNotFoundError("No such file: tui-td")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

        client = RpcClient("echo test")
        with pytest.raises(TUIConnectionError, match="not found"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_double_connect_raises(self, monkeypatch):
        """Connecting twice should raise TUIDriverError."""
        proc = FakeProcess()
        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tui-td", "version": "0.2.20"},
                },
            }
        )

        async def fake_subprocess(*args, **kwargs):
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

        client = RpcClient("echo test")
        await client.connect()
        try:
            with pytest.raises(TUIDriverError, match="Already connected"):
                await client.connect()
        finally:
            await client.close()


class TestRpcClientCall:
    """Tests for RpcClient.call()."""

    @pytest.mark.asyncio
    async def test_call_sends_tool_request(self, monkeypatch):
        """call() should send a proper tools/call request and return the result."""
        proc = FakeProcess()

        # Connect response
        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tui-td", "version": "0.2.20"},
                },
            }
        )

        async def fake_subprocess(*args, **kwargs):
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

        client = RpcClient("echo test")
        await client.connect()

        # Enqueue response for the tool call (id=2, after initialize id=1 + notification)
        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "hello world"}]},
            }
        )

        result = await client.call("tui_plain_text")
        assert result == "hello world"

        # Check the tool call request
        sent = json.loads(proc.stdin_data[-1])
        assert sent["method"] == "tools/call"
        assert sent["params"]["name"] == "tui_plain_text"

        await client.close()

    @pytest.mark.asyncio
    async def test_call_raises_on_error_result(self, monkeypatch):
        """call() should raise TUIConnectionError on isError=true."""
        proc = FakeProcess()
        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tui-td", "version": "0.2.20"},
                },
            }
        )

        async def fake_subprocess(*args, **kwargs):
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

        client = RpcClient("echo test")
        await client.connect()

        proc.enqueue_response(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": "ERROR: No TUI session active"}],
                    "isError": True,
                },
            }
        )

        with pytest.raises(TUIConnectionError, match="returned error"):
            await client.call("tui_state")

        await client.close()

    @pytest.mark.asyncio
    async def test_call_before_connect_raises(self):
        """Calling before connect() should raise TUIDriverError."""
        client = RpcClient("echo test")
        with pytest.raises(TUIDriverError, match="Not connected"):
            await client.call("tui_state")
