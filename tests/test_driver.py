"""Tests for the TUIDriver high-level API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tui_td.driver import TUIDriver
from tui_td.exceptions import TUIDriverError


class TestTUIDriverLifecycle:
    """Tests for driver start/close and context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """async with TUIDriver(...) should start and close cleanly."""
        with (
            patch("tui_td.driver.RpcClient") as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.call = AsyncMock(return_value="")
            mock_client.close = AsyncMock()
            mock_client_cls.return_value = mock_client

            async with TUIDriver("echo test") as tui:
                assert tui._started is True
                mock_client_cls.assert_called_once()
                mock_client.connect.assert_awaited_once()

            mock_client.call.assert_any_call("tui_close")
            mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_double_start_raises(self):
        """Starting twice should raise TUIDriverError."""
        with patch("tui_td.driver.RpcClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            driver = TUIDriver("echo test")
            await driver.start()
            try:
                with pytest.raises(TUIDriverError, match="already started"):
                    await driver.start()
            finally:
                await driver.close()

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """close() should be safe to call multiple times."""
        with patch("tui_td.driver.RpcClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            driver = TUIDriver("echo test")
            await driver.start()
            await driver.close()
            await driver.close()  # Should not raise


class TestTUIDriverErrors:
    """Tests for error states."""

    @pytest.mark.asyncio
    async def test_send_before_start_raises(self):
        """Calling send() before start() should raise TUIDriverError."""
        driver = TUIDriver("echo test")
        with pytest.raises(TUIDriverError, match="not started"):
            await driver.send("hello")

    @pytest.mark.asyncio
    async def test_send_key_before_start_raises(self):
        """Calling send_key() before start() should raise TUIDriverError."""
        driver = TUIDriver("echo test")
        with pytest.raises(TUIDriverError, match="not started"):
            await driver.send_key("enter")

    @pytest.mark.asyncio
    async def test_state_before_start_raises(self):
        """Calling state() before start() should raise TUIDriverError."""
        driver = TUIDriver("echo test")
        with pytest.raises(TUIDriverError, match="not started"):
            await driver.state()


class TestTUIDriverParsing:
    """Tests for response parsing helper methods."""

    def test_parse_no_matches(self):
        """_parse_text_matches should return empty list for 'No matches'."""
        result = TUIDriver._parse_text_matches("No matches found for: error")
        assert result == []

    def test_parse_single_match(self):
        """_parse_text_matches should parse a single match line."""
        raw = "Found 1 match(es) for: OK\n  row 3, col 10: [ OK ] Submit"
        result = TUIDriver._parse_text_matches(raw)
        assert len(result) == 1
        assert result[0].row == 3
        assert result[0].col == 10
        assert result[0].text == "[ OK ] Submit"

    def test_parse_no_elements(self):
        """_parse_elements should return empty list for 'No elements'."""
        result = TUIDriver._parse_elements("No elements found for role :button")
        assert result == []

    def test_parse_single_element(self):
        """_parse_elements should parse an element line."""
        raw = 'Found 1 element(s):\n  :button "OK" at [5,20] 6x1 (focused)'
        result = TUIDriver._parse_elements(raw)
        assert len(result) == 1
        assert result[0].role == "button"
        assert result[0].text == "OK"
        assert result[0].row == 5
        assert result[0].col == 20
        assert result[0].width == 6
        assert result[0].height == 1
        assert result[0].focused is True
        assert result[0].checked is False
        assert result[0].disabled is False


class TestTUIDriverMethods:
    """Tests for driver method calls (mocked RPC)."""

    @pytest.fixture
    def mock_rpc(self):
        """Create a mock RpcClient with connect/close/call."""
        with patch("tui_td.driver.RpcClient") as mock_cls:
            client = AsyncMock()
            client.connect = AsyncMock()
            client.call = AsyncMock()
            client.close = AsyncMock()
            mock_cls.return_value = client
            yield client

    @pytest.mark.asyncio
    async def test_send_delegates_to_rpc(self, mock_rpc):
        driver = TUIDriver("echo test")
        await driver.start()
        await driver.send("hello\n")
        mock_rpc.call.assert_any_call("tui_send", text="hello\n")
        await driver.close()

    @pytest.mark.asyncio
    async def test_send_key_delegates_to_rpc(self, mock_rpc):
        driver = TUIDriver("echo test")
        await driver.start()
        await driver.send_key("enter")
        mock_rpc.call.assert_any_call("tui_send_key", key="enter")
        await driver.close()

    @pytest.mark.asyncio
    async def test_state_ai_returns_aistatedata(self, mock_rpc):
        mock_rpc.call.return_value = (
            '{"size": {"rows": 40, "cols": 120}, '
            '"cursor": {"row": 1, "col": 0}, '
            '"text": "hello", '
            '"highlights": [], '
            '"summary": "ok"}'
        )
        driver = TUIDriver("echo test")
        await driver.start()
        state = await driver.state("ai")
        assert state.text == "hello"
        assert state.size.cols == 120
        await driver.close()

    @pytest.mark.asyncio
    async def test_state_full_returns_fullstatedata(self, mock_rpc):
        cell = (
            '{"char": "A", "fg": "default", "bg": "default", '
            '"bold": false, "italic": false, "underline": false, "blink": false}'
        )
        mock_rpc.call.return_value = (
            '{"size": {"rows": 2, "cols": 2}, '
            '"cursor": {"row": 0, "col": 0, "visible": true, "style": "block"}, '
            '"cursor_visible": true, "cursor_style": "block", '
            '"mouse_mode": null, "mouse_format": null, '
            f'"rows": [[{cell}, {cell}], [{cell}, {cell}]], '
            '"raw": "AA\\nAA"}'
        )
        driver = TUIDriver("echo test")
        await driver.start()
        state = await driver.state("full")
        assert state.size.rows == 2
        assert state.rows[0][0].char == "A"
        await driver.close()

    @pytest.mark.asyncio
    async def test_state_text_returns_string(self, mock_rpc):
        mock_rpc.call.return_value = "plain text content"
        driver = TUIDriver("echo test")
        await driver.start()
        text = await driver.state("text")
        assert text == "plain text content"
        await driver.close()

    @pytest.mark.asyncio
    async def test_plain_text_returns_string(self, mock_rpc):
        mock_rpc.call.return_value = "unformatted text"
        driver = TUIDriver("echo test")
        await driver.start()
        text = await driver.plain_text()
        assert text == "unformatted text"
        await driver.close()

    @pytest.mark.asyncio
    async def test_screenshot_parses_path(self, mock_rpc):
        mock_rpc.call.return_value = "OK: Screenshot saved to /tmp/test.png"
        driver = TUIDriver("echo test")
        await driver.start()
        path = await driver.screenshot()
        assert str(path) == "/tmp/test.png"
        await driver.close()

    @pytest.mark.asyncio
    async def test_screenshot_with_explicit_path(self, mock_rpc):
        mock_rpc.call.return_value = "OK: Screenshot saved to /custom/out.png"
        driver = TUIDriver("echo test")
        await driver.start()
        path = await driver.screenshot("/custom/out.png")
        mock_rpc.call.assert_any_call("tui_screenshot", path="/custom/out.png")
        assert str(path) == "/custom/out.png"
        await driver.close()

    @pytest.mark.asyncio
    async def test_find_text_parses_matches(self, mock_rpc):
        mock_rpc.call.return_value = (
            "Found 2 match(es) for: OK\n"
            "  row 3, col 10: [ OK ] Submit\n"
            "  row 8, col 5: [ OK ] Cancel"
        )
        driver = TUIDriver("echo test")
        await driver.start()
        matches = await driver.find_text("OK")
        assert len(matches) == 2
        assert matches[0].row == 3
        assert matches[0].col == 10
        assert matches[0].text == "[ OK ] Submit"
        assert matches[1].row == 8
        await driver.close()

    @pytest.mark.asyncio
    async def test_find_text_empty_result(self, mock_rpc):
        mock_rpc.call.return_value = "No matches found for: NOPE"
        driver = TUIDriver("echo test")
        await driver.start()
        matches = await driver.find_text("NOPE")
        assert matches == []
        await driver.close()

    @pytest.mark.asyncio
    async def test_check_exit_status_parses_status(self, mock_rpc):
        mock_rpc.call.return_value = "Exit status: 0"
        driver = TUIDriver("echo test")
        await driver.start()
        status = await driver.check_exit_status()
        assert status == 0
        await driver.close()

    @pytest.mark.asyncio
    async def test_close_before_start_noops(self, mock_rpc):
        """close() should not crash when called without start()."""
        driver = TUIDriver("echo test")
        await driver.close()  # should not raise
        mock_rpc.call.assert_not_called()

