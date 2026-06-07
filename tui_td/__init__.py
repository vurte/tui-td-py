"""tui-td-py — Official Python wrapper for tui-td.

TUI testing and automation for coding agents and terminal-based AI tools.
Communicates with the tui-td MCP server via JSON-RPC 2.0 over stdio.

Usage::

    import asyncio
    from tui_td import TUIDriver


    async def main() -> None:
        async with TUIDriver("htop", rows=24, cols=80) as tui:
            await tui.wait_for_stable()
            state = await tui.state()
            print(state.text)
            await tui.send_key("q")
            await tui.wait_for_exit()


    asyncio.run(main())
"""

from __future__ import annotations

from .driver import TUIDriver
from .exceptions import TUIConnectionError, TUIDriverError, TUITDError, TUITimeoutError
from .models import (
    AIStateData,
    Cell,
    Cursor,
    DiffEntry,
    Element,
    FullStateData,
    Highlight,
    Key,
    MatchMode,
    Size,
    SnapshotType,
    StateFormat,
    TextMatch,
)

__all__ = [
    # Driver
    "TUIDriver",
    # Exceptions
    "TUITDError",
    "TUIConnectionError",
    "TUITimeoutError",
    "TUIDriverError",
    # Models
    "Cell",
    "Cursor",
    "Size",
    "AIStateData",
    "FullStateData",
    "Highlight",
    "TextMatch",
    "Element",
    "DiffEntry",
    # Types
    "Key",
    "StateFormat",
    "MatchMode",
    "SnapshotType",
]

__version__ = "0.1.0"
