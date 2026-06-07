"""TUI Driver — the main high-level API for tui-td-py.

Provides ``TUIDriver``, an async context manager that wraps the
tui-td MCP server via JSON-RPC 2.0 over stdio.

Usage::

    async with TUIDriver("htop") as tui:
        await tui.wait_for_stable()
        state = await tui.state()
        print(state.text)
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path
from types import TracebackType
from typing import Any

from .exceptions import TUIDriverError, TUITimeoutError
from .models import (
    AIStateData,
    Element,
    FullStateData,
    Key,
    MatchMode,
    SnapshotType,
    StateFormat,
    TextMatch,
)
from .rpc import RpcClient

logger = logging.getLogger(__name__)


class TUIDriver:
    """Async driver for controlling a TUI application via tui-td.

    Connects to the ``tui-td serve`` MCP server as a subprocess and
    exposes all tui-td functionality as clean Python methods.

    Args:
        command: The shell command to run (e.g. ``"htop"``, ``"vim file.txt"``).
        rows: Terminal height in rows.
        cols: Terminal width in columns.
        timeout: Default timeout in seconds for wait operations.
        chdir: Working directory for the command (not supported via MCP —
            set before starting if needed).
        executable: Path to the ``tui-td`` executable.

    Example::

        import asyncio
        from tui_td import TUIDriver


        async def main():
            async with TUIDriver("echo 'Hello World'") as tui:
                await tui.wait_for_stable()
                text = await tui.plain_text()
                print(text)


        asyncio.run(main())
    """

    def __init__(
        self,
        command: str,
        *,
        rows: int = 40,
        cols: int = 120,
        timeout: float = 30.0,
        chdir: str | None = None,
        executable: str = "tui-td",
    ) -> None:
        self._command = command
        self._rows = rows
        self._cols = cols
        self._timeout = timeout
        self._chdir = chdir
        self._executable = executable

        self._rpc: RpcClient | None = None
        self._started: bool = False
        self._exit_status: int | None = None

    # ── Context Manager ──────────────────────────────────────

    async def __aenter__(self) -> TUIDriver:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ── Lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        """Start the TUI application and connect to the MCP server.

        Raises:
            TUIDriverError: If already started.
            TUIConnectionError: If connection fails.
        """
        if self._started:
            raise TUIDriverError("TUIDriver already started.")

        self._rpc = RpcClient(
            self._command,
            rows=self._rows,
            cols=self._cols,
            timeout=self._timeout,
            executable=self._executable,
        )
        await self._rpc.connect()

        # Start the actual TUI process via tui_start
        await self._rpc.call(
            "tui_start",
            command=self._command,
            rows=self._rows,
            cols=self._cols,
            timeout=int(self._timeout),
        )

        self._started = True
        logger.info("TUIDriver started: %s (%dx%d)", self._command, self._cols, self._rows)

    async def close(self) -> None:
        """Close the TUI session and clean up resources.

        Safe to call multiple times; no-op if already closed.
        """
        if not self._started:
            return

        if self._rpc:
            with contextlib.suppress(Exception):
                await self._rpc.call("tui_close")
            await self._rpc.close()
            self._rpc = None

        self._started = False
        self._exit_status = None
        logger.info("TUIDriver closed.")

    # ── Input ─────────────────────────────────────────────────

    async def send(self, text: str) -> None:
        """Send text to the TUI.

        Use ``"\\n"`` for Enter, ``"\\t"`` for Tab.

        Args:
            text: The text to send (written as-is).
        """
        self._ensure_running()
        assert self._rpc is not None
        await self._rpc.call("tui_send", text=text)

    async def send_key(self, key: Key | str) -> None:
        """Send a special key press to the TUI.

        Args:
            key: Key name. Supported values: ``"enter"``, ``"tab"``,
                ``"escape"``, ``"up"``, ``"down"``, ``"left"``, ``"right"``,
                ``"backspace"``, ``"ctrl_c"``, ``"ctrl_d"``, ``"ctrl_z"``,
                ``"page_up"``, ``"page_down"``, ``"home"``, ``"end"``,
                ``"delete"``.
        """
        self._ensure_running()
        assert self._rpc is not None
        await self._rpc.call("tui_send_key", key=key)

    # ── State Queries ─────────────────────────────────────────

    async def state(self, format: StateFormat = "ai") -> AIStateData | FullStateData | str:
        """Get the current terminal state.

        Args:
            format: Output format. ``"ai"`` returns :class:`AIStateData`
                (compact, text + highlights). ``"full"`` returns
                :class:`FullStateData` (complete cell grid).
                ``"text"`` returns a plain string.

        Returns:
            The state in the requested format.
        """
        self._ensure_running()
        assert self._rpc is not None
        raw = await self._rpc.call("tui_state", format=format)

        if format == "text":
            return raw

        data = json.loads(raw)
        if format == "full":
            return FullStateData.model_validate(data)
        return AIStateData.model_validate(data)

    async def plain_text(self) -> str:
        """Get the current terminal content as plain text (ANSI stripped)."""
        self._ensure_running()
        assert self._rpc is not None
        return await self._rpc.call("tui_plain_text")

    async def screenshot(self, path: str | None = None) -> Path:
        """Capture a PNG screenshot of the terminal.

        Args:
            path: Output file path. Auto-generated under ``/tmp`` if omitted.

        Returns:
            Path to the saved screenshot.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {}
        if path:
            kwargs["path"] = path
        result = await self._rpc.call("tui_screenshot", **kwargs)
        # Parse path from result message: "OK: Screenshot saved to /tmp/..."
        file_path = result.split("saved to ", 1)[-1].strip()
        return Path(file_path)

    async def html_render(self, path: str | None = None) -> str:
        """Render the terminal as HTML.

        Args:
            path: If provided, saves HTML to this file and returns the path.
                If omitted, returns the HTML content as a string.

        Returns:
            HTML content or save confirmation message.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {}
        if path:
            kwargs["path"] = path
        return await self._rpc.call("tui_html_render", **kwargs)

    # ── Wait Operations ───────────────────────────────────────

    async def wait_for_text(self, text: str, timeout: float | None = None) -> str:
        """Wait until the terminal output contains the given text.

        Args:
            text: Text to wait for.
            timeout: Custom timeout in seconds. Uses driver default if omitted.

        Returns:
            The current terminal state as AI-format text.

        Raises:
            TUITimeoutError: If the text doesn't appear within the timeout.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {"text": text}
        if timeout is not None:
            kwargs["timeout"] = int(timeout)

        try:
            result = await self._rpc.call("tui_wait_for_text", **kwargs)
        except Exception as exc:
            if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                raise TUITimeoutError(f"wait_for_text({text!r})", timeout or self._timeout) from exc
            raise
        return result

    async def wait_for_stable(self, timeout: float | None = None) -> str:
        """Wait until the terminal output stabilizes (300ms of silence).

        Args:
            timeout: Custom timeout in seconds.

        Returns:
            The current terminal state as AI-format text.

        Raises:
            TUITimeoutError: If output doesn't stabilize within the timeout.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {}
        if timeout is not None:
            kwargs["timeout"] = int(timeout)

        try:
            result = await self._rpc.call("tui_wait_for_stable", **kwargs)
        except Exception as exc:
            if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                raise TUITimeoutError("wait_for_stable", timeout or self._timeout) from exc
            raise
        return result

    async def wait_for_exit(self) -> int:
        """Wait until the TUI process exits.

        Returns:
            The exit status code (0 = success, non-zero = error).

        Raises:
            TUITimeoutError: If the process doesn't exit within the timeout.
        """
        self._ensure_running()
        assert self._rpc is not None
        result = await self._rpc.call("tui_wait_for_exit")
        # Parse exit status from "OK: Process exited with status N"
        try:
            self._exit_status = int(result.rsplit(None, 1)[-1])
        except (ValueError, IndexError):
            self._exit_status = None
        return -1 if self._exit_status is None else self._exit_status

    # ── Exit Status ───────────────────────────────────────────

    @property
    def exit_status(self) -> int | None:
        """The exit status of the TUI process (``None`` if still running)."""
        if not self._started or self._rpc is None:
            return self._exit_status

        # Don't make this async — callers can use await driver.wait_for_exit()
        return self._exit_status

    async def check_exit_status(self) -> int | None:
        """Query the current exit status (non-blocking).

        Returns:
            Exit code if the process has exited, ``None`` if still running.
        """
        self._ensure_running()
        assert self._rpc is not None
        result = await self._rpc.call("tui_exit_status")
        if "Exit status:" in result:
            with contextlib.suppress(ValueError, IndexError):
                self._exit_status = int(result.rsplit(None, 1)[-1])
        return self._exit_status

    # ── Text Search ───────────────────────────────────────────

    async def find_text(self, pattern: str, match: MatchMode = "partial") -> list[TextMatch]:
        """Search for text or regex pattern in the terminal state.

        Args:
            pattern: Text or regex pattern to search for.
            match: Match mode — ``"partial"`` (substring, default),
                ``"exact"`` (whole row), or ``"regex"`` (Ruby regex).

        Returns:
            List of matches with position, text, and full line context.
        """
        self._ensure_running()
        assert self._rpc is not None
        result = await self._rpc.call("tui_find_text", pattern=pattern, match=match)
        return self._parse_text_matches(result)

    # ── UI Elements ───────────────────────────────────────────

    async def find_elements(
        self,
        *,
        role: str | None = None,
        text: str | None = None,
        checked: bool | None = None,
        disabled: bool | None = None,
    ) -> list[Element]:
        """Find UI elements in the terminal state.

        Uses heuristic analysis to detect buttons, checkboxes, dialogs,
        inputs, labels, menus, tabs, status bars, and progress bars.

        Args:
            role: Filter by role (e.g. ``"button"``, ``"dialog"``).
            text: Filter by visible text (partial match).
            checked: Filter by checked state (checkboxes).
            disabled: Filter by disabled state.

        Returns:
            List of matching elements.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {}
        if role:
            kwargs["role"] = role
        if text:
            kwargs["text"] = text
        if checked is not None:
            kwargs["checked"] = checked
        if disabled is not None:
            kwargs["disabled"] = disabled

        result = await self._rpc.call("tui_find_elements", **kwargs)
        return self._parse_elements(result)

    async def element_actions(self, role: str, text: str | None = None) -> str:
        """Get interaction actions for a detected UI element.

        Args:
            role: Element role (e.g. ``"button"``).
            text: Filter by visible text.

        Returns:
            A description of available actions (click, type, press_key).
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {"role": role}
        if text:
            kwargs["text"] = text
        return await self._rpc.call("tui_element_actions", **kwargs)

    # ── Diff ──────────────────────────────────────────────────

    async def diff(self, snapshot: dict[str, Any], *, chars_only: bool = False) -> str:
        """Compare current state against a previous snapshot.

        Args:
            snapshot: A previously saved state snapshot.
            chars_only: If True, only compare character differences
                        (ignore color/style).

        Returns:
            A human-readable diff summary.
        """
        self._ensure_running()
        assert self._rpc is not None
        return await self._rpc.call("tui_diff", snapshot=snapshot, chars_only=chars_only)

    # ── Annotations ───────────────────────────────────────────

    async def annotate_element(
        self,
        role: str,
        *,
        row: int,
        col: int,
        width: int = 1,
        height: int = 1,
        text: str | None = None,
    ) -> None:
        """Manually register a UI element at a specific region.

        The annotation is picked up by subsequent :meth:`find_elements` calls.

        Args:
            role: Element role (e.g. ``"button"``, ``"dialog"``).
            row: Top row of the element.
            col: Left column of the element.
            width: Width in columns.
            height: Height in rows.
            text: Visible text label.
        """
        self._ensure_running()
        assert self._rpc is not None
        kwargs: dict[str, Any] = {
            "role": role,
            "row": row,
            "col": col,
            "width": width,
            "height": height,
        }
        if text:
            kwargs["text"] = text
        await self._rpc.call("tui_annotate_element", **kwargs)

    # ── Snapshots ─────────────────────────────────────────────

    async def save_snapshot(self, name: str, *, type: SnapshotType = "text") -> None:
        """Save the current terminal state as a named snapshot.

        Args:
            name: Snapshot name (e.g. ``"login_screen"``).
            type: Snapshot type — ``"text"`` (default), ``"full"``,
                  ``"png"``, ``"html"``, or ``"all"``.
        """
        self._ensure_running()
        assert self._rpc is not None
        await self._rpc.call("tui_save_snapshot", name=name, type=type)

    async def assert_snapshot(self, name: str, *, type: SnapshotType = "text") -> str:
        """Assert current state matches a named snapshot.

        Creates the snapshot on first run; compares on subsequent runs.
        Set ``UPDATE_SNAPSHOTS=1`` to force update.

        Args:
            name: Snapshot name.
            type: Snapshot type.

        Returns:
            Snapshot comparison result message.
        """
        self._ensure_running()
        assert self._rpc is not None
        return await self._rpc.call("tui_assert_snapshot", name=name, type=type)

    # ── Video Recording ───────────────────────────────────────

    async def record_start(
        self,
        path: str,
        *,
        framerate: int = 30,
        codec: str = "libx264",
        quality: str = "high",
    ) -> None:
        """Start recording the TUI session as a video.

        Requires ``ffmpeg`` installed on the system.

        Args:
            path: Output file path (e.g. ``"/tmp/session.mp4"``).
            framerate: Frames per second.
            codec: Video codec (``"libx264"``, ``"libx265"``, ``"libvpx-vp9"``).
            quality: Quality preset (``"high"``, ``"medium"``, ``"low"``).
        """
        self._ensure_running()
        assert self._rpc is not None
        await self._rpc.call(
            "tui_record_start",
            path=path,
            framerate=framerate,
            codec=codec,
            quality=quality,
        )

    async def record_stop(self) -> Path:
        """Stop video recording and finalize the file.

        Returns:
            Path to the saved video file.
        """
        self._ensure_running()
        assert self._rpc is not None
        result = await self._rpc.call("tui_record_stop")
        file_path = result.split("saved to ", 1)[-1].strip()
        return Path(file_path)

    async def record_status(self) -> bool:
        """Check if video recording is active.

        Returns:
            ``True`` if recording is in progress.
        """
        self._ensure_running()
        assert self._rpc is not None
        result = await self._rpc.call("tui_record_status")
        return "active" in result.lower()

    # ── Helpers ───────────────────────────────────────────────

    def _ensure_running(self) -> None:
        """Raise if the driver is not started."""
        if not self._started or self._rpc is None:
            raise TUIDriverError(
                "TUIDriver not started. Use 'async with TUIDriver(...)' or call start()."
            )

    @staticmethod
    def _parse_text_matches(raw: str) -> list[TextMatch]:
        """Parse text match output from tui_find_text into TextMatch objects."""
        matches: list[TextMatch] = []
        if raw.startswith("No matches found"):
            return matches

        for line in raw.split("\n"):
            # Format: "  row N, col M: full line text"
            if line.startswith("  row "):
                try:
                    parts = line.strip().split(": ", 1)
                    meta = parts[0]  # "row N, col M"
                    full_line = parts[1] if len(parts) > 1 else ""
                    row_part, col_part = meta.split(", ", 1)
                    row = int(row_part.split(" ", 1)[1])
                    col = int(col_part.split(" ", 1)[1])
                    matches.append(
                        TextMatch(
                            row=row,
                            col=col,
                            text=full_line.strip(),
                            full_line=full_line,
                        )
                    )
                except (ValueError, IndexError):
                    logger.debug("Could not parse text match line: %s", line)
        return matches

    @staticmethod
    def _parse_elements(raw: str) -> list[Element]:
        """Parse element list output from tui_find_elements into Element objects."""
        elements: list[Element] = []
        if raw.startswith("No elements found"):
            return elements

        for line in raw.split("\n"):
            # Format: "  :role "text" at [row,col] WxH (checked) (disabled) (focused)"
            if not line.startswith("  :"):
                continue

            try:
                rest = line.strip()
                # Extract flags before parsing structure
                checked = "(checked)" in rest
                disabled = "(disabled)" in rest
                focused = "(focused)" in rest

                # Parse role: everything between ": " and next space/quote
                role_end = rest.index(" ")
                role = rest[1:role_end]  # skip ":" prefix (after strip)

                # Position cursor past the role
                pos = role_end + 1

                # Parse quoted text if present
                text = None
                if pos < len(rest) and rest[pos] == '"':
                    quote_end = rest.index('"', pos + 1)
                    text = rest[pos + 1 : quote_end]
                    pos = quote_end + 1

                # Skip " at " separator
                at_marker = " at ["
                at_idx = rest.find(at_marker, pos)
                if at_idx == -1:
                    continue
                pos = at_idx + len(at_marker)  # now at "row,col]"

                # Parse row,col
                bracket_end = rest.index("]", pos)
                coords = rest[pos:bracket_end]
                row, col = map(int, coords.split(","))
                pos = bracket_end + 2  # skip "] "

                # Parse WxH
                dim_end = rest.index(" ", pos) if " " in rest[pos:] else len(rest)
                dims = rest[pos:dim_end]
                w, h = map(int, dims.split("x"))

                elements.append(
                    Element(
                        role=role,  # type: ignore[arg-type]
                        text=text,
                        row=row,
                        col=col,
                        width=w,
                        height=h,
                        checked=checked,
                        disabled=disabled,
                        focused=focused,
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.debug("Could not parse element line: %s (%s)", line, exc)
        return elements
