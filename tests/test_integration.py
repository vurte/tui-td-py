"""Integration tests against a real tui-td MCP server.

These tests require ``tui-td`` to be installed (``gem install tui-td``).
Skip gracefully if not available.
"""

from __future__ import annotations

import pytest

from tui_td import TUIDriver


def _tui_td_available() -> bool:
    """Check if tui-td is installed and runnable."""
    import shutil

    return shutil.which("tui-td") is not None


requires_tui_td = pytest.mark.skipif(
    not _tui_td_available(),
    reason="tui-td is not installed (run: gem install tui-td)",
)


class TestIntegrationEcho:
    """Integration tests using echo as the TUI command."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_echo_hello_world(self):
        """Start echo, wait for stable, check output."""
        async with TUIDriver("echo 'Hello World'") as tui:
            await tui.wait_for_stable(timeout=10)
            text = await tui.plain_text()
            assert "Hello World" in text

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_ls_output(self):
        """Run ls and verify directory listing."""
        async with TUIDriver("ls -1 /", rows=5, cols=80) as tui:
            await tui.wait_for_stable(timeout=10)
            text = await tui.plain_text()
            assert len(text.strip()) > 0
            # Common directories that should appear
            assert any(d in text for d in ["bin", "tmp", "usr", "etc", "home"])

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_wait_for_text(self):
        """wait_for_text should find specific text."""
        async with TUIDriver("echo 'READY>'", rows=5, cols=80) as tui:
            result = await tui.wait_for_text("READY", timeout=10)
            assert "READY" in result

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_text_search(self):
        """find_text should locate patterns."""
        async with TUIDriver(
            "echo -e 'Line 1: OK\\nLine 2: ERROR\\nLine 3: OK'",
            rows=5,
            cols=80,
        ) as tui:
            await tui.wait_for_stable(timeout=10)
            matches = await tui.find_text("ERROR")
            assert len(matches) >= 1
            assert any("ERROR" in m.text for m in matches)

            matches = await tui.find_text("OK")
            assert len(matches) >= 2


class TestIntegrationStateFormats:
    """Tests for different state output formats."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_state_ai_format(self):
        """AI format should return structured data with text."""
        async with TUIDriver("echo 'DATA_CHECK_42'", rows=5, cols=80) as tui:
            await tui.wait_for_stable(timeout=10)
            state = await tui.state("ai")
            assert "DATA_CHECK_42" in state.text
            assert state.size.cols == 80
            assert state.cursor is not None

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_state_full_format(self):
        """Full format should return cell grid."""
        async with TUIDriver("echo 'XY'", rows=5, cols=30) as tui:
            await tui.wait_for_stable(timeout=10)
            state = await tui.state("full")
            assert state.size.cols == 30
            assert len(state.rows) == 5
            assert state.raw  # raw ANSI should not be empty

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_state_text_format(self):
        """Text format should return a plain string."""
        async with TUIDriver("echo -n 'PURE_TEXT'", rows=5, cols=80) as tui:
            await tui.wait_for_stable(timeout=10)
            text = await tui.state("text")
            assert isinstance(text, str)
            assert "PURE_TEXT" in text


class TestIntegrationInteractive:
    """Tests that involve send/respond interaction."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_send_echo_back(self):
        """Program that reads a line and echoes it back."""
        script = "read -r line; echo GOT: $line"
        async with TUIDriver(f"bash -c '{script}'", rows=5, cols=80) as tui:
            await tui.wait_for_stable(timeout=10)
            await tui.send("hello\n")
            await tui.wait_for_stable(timeout=10)
            text = await tui.plain_text()
            assert "GOT: hello" in text

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_send_key_ctrl_c(self):
        """ctrl_c should exit a sleeping process."""
        async with TUIDriver("sleep 30", rows=5, cols=80, timeout=5) as tui:
            await tui.wait_for_stable(timeout=10)
            await tui.send_key("ctrl_c")
            exit_code = await tui.wait_for_exit()
            assert exit_code != 0  # killed by signal


class TestIntegrationExitStatus:
    """Tests for exit status handling."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_exit_success(self):
        """Normal exit should return 0."""
        async with TUIDriver("echo ok", rows=5, cols=80) as tui:
            exit_code = await tui.wait_for_exit()
            assert exit_code == 0

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_exit_failure(self):
        """Failed command should return non-zero."""
        async with TUIDriver("false", rows=5, cols=80) as tui:
            exit_code = await tui.wait_for_exit()
            assert exit_code != 0

    # Note: check_exit_status() wraps tui_exit_status, which blocks in
    # tui-td until the process exits (Process.detach → Thread#value).
    # It cannot return None for a running process — this is a tui-td
    # API limitation. Use wait_for_exit() to get the final exit code.


class TestIntegrationFindElements:
    """Tests for UI element detection."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_find_elements_all(self):
        """find_elements() without filters should return a list."""
        # Use a short-lived command; just verify the method returns a list
        async with TUIDriver("echo '[ OK ] Cancel'", rows=5, cols=40) as tui:
            await tui.wait_for_stable(timeout=10)
            elements = await tui.find_elements()
            assert isinstance(elements, list)

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_find_elements_button(self):
        """find_elements(role='button') should find button-like text."""
        async with TUIDriver(
            "echo '[ OK ]  (Cancel)  <Submit>'", rows=5, cols=40
        ) as tui:
            await tui.wait_for_stable(timeout=10)
            buttons = await tui.find_elements(role="button")
            assert isinstance(buttons, list)


class TestIntegrationEdgeCases:
    """Edge case and error handling tests."""

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_unicode_output(self):
        """Should handle Unicode characters."""
        async with TUIDriver("echo 'Héllo Wörld 日本語'", rows=5, cols=80) as tui:
            await tui.wait_for_stable(timeout=10)
            text = await tui.plain_text()
            assert "Héllo" in text
            assert "Wörld" in text
            assert "日本語" in text

    @requires_tui_td
    @pytest.mark.asyncio
    async def test_long_output(self):
        """Should handle longer command output."""
        async with TUIDriver(
            'bash -c "for i in \\$(seq 1 20); do echo Line \\$i; done"',
            rows=30,
            cols=80,
        ) as tui:
            await tui.wait_for_stable(timeout=10)
            text = await tui.plain_text()
            assert "Line 1" in text
            assert "Line 20" in text
