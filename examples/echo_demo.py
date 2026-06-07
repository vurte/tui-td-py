#!/usr/bin/env python3
"""Demo: Drive a simple TUI application with tui-td-py.

Requires tui-td to be installed: gem install tui-td
"""

from __future__ import annotations

import asyncio

from tui_td import TUIDriver


async def main() -> None:
    print("Starting tui-td-py demo...\n")

    async with TUIDriver("echo 'Hello from tui-td-py!'", rows=5, cols=80) as tui:
        # Wait for output to stabilize
        await tui.wait_for_stable(timeout=10)

        # Get plain text
        plain = await tui.plain_text()
        print(f"Plain text:\n{plain}")

        # Get AI-friendly state
        state = await tui.state("ai")
        print(f"AI State: {state.summary}")

        # Search for text
        matches = await tui.find_text("tui-td-py")
        print(f"Found {len(matches)} matches for 'tui-td-py'")

        # Take a screenshot
        screenshot_path = await tui.screenshot()
        print(f"Screenshot saved to: {screenshot_path}")

    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
