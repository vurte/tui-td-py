#!/usr/bin/env python3
"""Snapshot and diff workflow: capture before/after states, compare them.

Demonstrates:
- Capturing state snapshots
- Performing actions between captures
- Diffing terminal states cell-by-cell
"""

from __future__ import annotations

import asyncio
import json

from tui_td import TUIDriver


async def main() -> None:
    cmd = "echo -e 'Line 1: OK\\nLine 2: TODO\\nLine 3: OK'"
    async with TUIDriver(cmd, rows=5, cols=80) as tui:
        await tui.wait_for_stable(timeout=10)

        # ── 1. Capture the initial state ────────────────────────────
        print("=== Initial State ===")
        initial_state = await tui.state("full")
        print(f"  Size: {initial_state.size.cols}x{initial_state.size.rows}")
        for i, row in enumerate(initial_state.rows):
            chars = "".join(cell.char for cell in row).rstrip()
            if chars.strip():
                print(f"  Row {i}: {chars}")

        # Convert to plain dict for snapshot comparison
        snapshot = json.loads(initial_state.model_dump_json())

        # ── 2. Diff against the same state (should be empty) ────────
        print("\n=== Diff (initial vs initial) ===")
        result = await tui.diff(snapshot, chars_only=True)
        print(f"  {result}")

        # ── 3. Diff against a deliberately modified snapshot ────────
        modified = json.loads(json.dumps(snapshot))
        # Change the first char of row 0
        if modified["rows"][0][0]["char"] == "L":
            modified["rows"][0][0]["char"] = "X"

        print("\n=== Diff (initial vs modified) ===")
        result = await tui.diff(modified, chars_only=True)
        print(f"  {result}")


if __name__ == "__main__":
    asyncio.run(main())
