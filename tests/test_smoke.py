"""Smoke test — quick end-to-end validation of the full tui-td-py stack.

Verifies: connect → start → wait_for_stable → state → plain_text →
find_text → screenshot → send_key → wait_for_exit → close

Requires tui-td to be installed.
"""

from __future__ import annotations

import shutil

import pytest

from tui_td import TUIDriver


def _tui_td_present() -> bool:
    return shutil.which("tui-td") is not None


pytestmark = pytest.mark.skipif(
    not _tui_td_present(),
    reason="tui-td not installed",
)


@pytest.mark.asyncio
async def test_full_lifecycle_echo():
    """Complete lifecycle: echo → capture → search → close."""
    async with TUIDriver("echo 'SMOKE_TEST_OK_12345'", rows=5, cols=80) as tui:
        # 1. Wait for output
        await tui.wait_for_stable(timeout=10)

        # 2. Read state in all three formats
        ai_state = await tui.state("ai")
        assert isinstance(ai_state.text, str)
        assert "SMOKE_TEST_OK_12345" in ai_state.text

        full_state = await tui.state("full")
        assert full_state.size.cols == 80
        assert full_state.size.rows == 5

        plain = await tui.plain_text()
        assert "SMOKE_TEST_OK_12345" in plain

        # 3. Text search
        matches = await tui.find_text("SMOKE_TEST")
        assert len(matches) >= 1
        assert matches[0].text == "SMOKE_TEST_OK_12345"

        # 4. Screenshot
        path = await tui.screenshot()
        assert path.suffix == ".png"
        assert path.exists()
        path.unlink()  # cleanup

        # 5. No elements for echo
        elements = await tui.find_elements()
        assert isinstance(elements, list)


@pytest.mark.asyncio
async def test_smoke_send_and_respond():
    """Send input to an interactive program and verify response."""
    # Use cat to echo back everything it receives
    async with TUIDriver("cat", rows=5, cols=80) as tui:
        await tui.wait_for_stable(timeout=10)
        await tui.send("Hello World\n")
        await tui.wait_for_stable(timeout=10)
        text = await tui.plain_text()
        assert "Hello World" in text
        await tui.send_key("ctrl_c")
        await tui.wait_for_exit()


@pytest.mark.asyncio
async def test_smoke_state_formats():
    """All three state formats should work correctly."""
    async with TUIDriver("echo 'TEST'", rows=5, cols=40) as tui:
        await tui.wait_for_stable(timeout=10)

        # ai format
        ai = await tui.state("ai")
        assert "TEST" in ai.text
        assert ai.cursor.row >= 0
        assert ai.size.cols == 40

        # full format
        full = await tui.state("full")
        assert len(full.rows) == 5
        assert len(full.rows[0]) == 40
        assert any(cell.char == "T" for row in full.rows for cell in row)

        # text format
        text = await tui.state("text")
        assert isinstance(text, str)
        assert "TEST" in text
