#!/usr/bin/env python3
"""Basic TUI automation: start an app, capture state, search text, take screenshot.

Shows the most common tui-td-py patterns:
- Context manager for lifecycle
- Reading terminal state in all three formats
- Text search with regex
- UI element detection
- Screenshot capture
"""

from __future__ import annotations

import asyncio

from tui_td import TUIDriver


async def main() -> None:
    async with TUIDriver("echo 'Hello from tui-td-py!'", rows=5, cols=80) as tui:
        # ── 1. Wait for output to appear ──────────────────────────
        await tui.wait_for_stable(timeout=10)

        # ── 2. Read state in all three formats ─────────────────────
        print("=== AI State (compact) ===")
        ai_state = await tui.state("ai")
        print(f"  Size: {ai_state.size.cols}x{ai_state.size.rows}")
        print(f"  Cursor: [{ai_state.cursor.row}, {ai_state.cursor.col}]")
        print(f"  Text: {ai_state.text.strip()}")
        print(f"  Summary: {ai_state.summary}")
        for hl in ai_state.highlights:
            print(f"  Highlight row {hl.row}: {hl.text} (bold={hl.bold})")

        print("\n=== Full State (cell grid) ===")
        full = await tui.state("full")
        # Print only non-empty rows
        for i, row in enumerate(full.rows):
            chars = "".join(cell.char for cell in row).rstrip()
            if chars:
                print(f"  Row {i}: {chars}")

        print("\n=== Plain Text ===")
        text = await tui.plain_text()
        print(f"  {text.strip()}")

        # ── 3. Search for text ─────────────────────────────────────
        print("\n=== Text Search ===")
        matches = await tui.find_text("tui-td-py", match="partial")
        for m in matches:
            print(f"  Found at [{m.row},{m.col}]: {m.full_line}")

        # Regex search
        matches = await tui.find_text(r"Hello|World", match="regex")
        for m in matches:
            print(f"  Regex match at [{m.row},{m.col}]: {m.full_line}")

        # ── 4. Check for UI elements ───────────────────────────────
        print("\n=== UI Elements ===")
        elements = await tui.find_elements()
        if elements:
            for el in elements:
                print(f"  :{el.role} '{el.text}' at [{el.row},{el.col}] {el.width}x{el.height}")
        else:
            print("  No UI elements detected (expected for plain echo)")

        # ── 5. Screenshot ──────────────────────────────────────────
        screenshot_path = await tui.screenshot()
        print("\n=== Screenshot ===")
        print(f"  Saved to: {screenshot_path}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
