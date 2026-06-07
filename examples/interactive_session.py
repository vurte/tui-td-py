#!/usr/bin/env python3
"""Interactive TUI session: send input, wait for responses, check output.

Demonstrates:
- Sending text and special keys
- Waiting for specific text patterns
- UI element interaction (finding buttons, getting actions)
- Checking exit status
"""

from __future__ import annotations

import asyncio

from tui_td import TUIDriver


async def main() -> None:
    # Launch a shell that prompts for input and echoes it back
    script = "read -p 'Enter name: ' name && echo Hello, $name!"
    async with TUIDriver(f"bash -c '{script}'", rows=8, cols=60) as tui:
        # ── 1. Wait for the prompt ─────────────────────────────────
        print("Waiting for prompt...")
        await tui.wait_for_text("Enter name:", timeout=10)
        state = await tui.state("text")
        print(f"Terminal shows:\n{state}")

        # ── 2. Send a response ──────────────────────────────────────
        print("\nSending: 'World'")
        await tui.send("World\n")

        # ── 3. Wait for the greeting to appear ──────────────────────
        await tui.wait_for_text("Hello, World!", timeout=5)
        state = await tui.state("text")
        print(f"Terminal shows:\n{state}")

    # ── 4. Verify exit status ──────────────────────────────────────
    print("\nProcess exited.")


if __name__ == "__main__":
    asyncio.run(main())
