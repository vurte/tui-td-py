# tui-td-py

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Official Python wrapper for [tui-td](https://github.com/tui-td/tui-td) — TUI testing and automation for coding agents and terminal-based AI tools.

**tui-td-py** communicates with the `tui-td serve` MCP server via JSON-RPC 2.0 over stdio. Start any TUI in a virtual terminal, send input, and analyze output — as structured Python objects, plain text, PNG screenshots, or HTML renders.

## Prerequisites

| Software | Minimum | Installation |
|----------|---------|-------------|
| **Python** | 3.10+ | [python.org](https://python.org) or `brew install python` |
| **Ruby** | 3.0+ | [rbenv](https://github.com/rbenv/rbenv) or `brew install ruby` |
| **tui-td** (Ruby gem) | 0.2.20+ | `gem install tui-td` |

```bash
# Install Ruby + tui-td
brew install ruby
gem install tui-td

# Verify
tui-td --version
# => tui-td 0.2.20
```

## Installation

```bash
pip install git+https://gitlab.com/haluk786/tui-td-py.git
```

## Quick Start

```python
import asyncio
from tui_td import TUIDriver


async def main() -> None:
    async with TUIDriver("echo 'Hello World'", rows=5, cols=80) as tui:
        await tui.wait_for_stable()
        text = await tui.plain_text()
        print(text)


asyncio.run(main())
```

More examples in [`examples/`](examples/):
- [`basic_tui_driver.py`](examples/basic_tui_driver.py) — States, Search, Elements, Screenshot
- [`interactive_session.py`](examples/interactive_session.py) — Send/Wait/Respond Workflow
- [`snapshot_diff.py`](examples/snapshot_diff.py) — Before/After Snapshots + Diff

## Usage

### Start and Stop

```python
# Context manager (recommended)
async with TUIDriver("my_tui_app") as tui:
    ...

# Manual lifecycle
tui = TUIDriver("my_tui_app")
await tui.start()
# ... use tui ...
await tui.close()
```

### Send Input

```python
# Send text (use \n for Enter)
await tui.send("hello\n")

# Send special keys
await tui.send_key("enter")
await tui.send_key("up")
await tui.send_key("ctrl_c")
await tui.send_key("escape")
```

### Read State

```python
# AI-friendly compact state (text + highlights)
state = await tui.state("ai")
print(state.text)
for hl in state.highlights:
    print(f"  row {hl.row}: {hl.text} (bold={hl.bold}, fg={hl.fg})")

# Full cell grid with colors
full = await tui.state("full")
for row in full.rows:
    for cell in row:
        if cell.fg != "default":
            print(f"Colored char: {cell.char} fg={cell.fg}")

# Plain text only
text = await tui.plain_text()
```

### Wait Operations

```python
# Wait for specific text to appear
await tui.wait_for_text("> ", timeout=10)

# Wait for output to stabilize (300ms of silence)
await tui.wait_for_stable()

# Wait for process to finish
exit_code = await tui.wait_for_exit()
```

### Search and Elements

```python
# Search for text or regex
matches = await tui.find_text("ERROR", match="partial")
for m in matches:
    print(f"Found at [{m.row},{m.col}]: {m.full_line}")

# Find UI elements by role
buttons = await tui.find_elements(role="button")
dialogs = await tui.find_elements(role="dialog")
inputs = await tui.find_elements(role="input")

# Element with filters
checked = await tui.find_elements(role="checkbox", checked=True)

# Get actions for an element
actions = await tui.element_actions("button", text="OK")
print(actions)
```

### Screenshots and HTML

```python
# PNG screenshot
path = await tui.screenshot()
print(f"Screenshot: {path}")

# HTML render (inline)
html = await tui.html_render()

# HTML render (save to file)
await tui.html_render("/tmp/output.html")
```

### Snapshots and Diff

```python
# Save a named snapshot
await tui.save_snapshot("login_screen", type="text")

# Assert current state matches (creates on first run)
result = await tui.assert_snapshot("login_screen")
print(result)

# Diff against a previously saved state
diff = await tui.diff(previous_state_data, chars_only=True)
```

### Video Recording

```python
# Start recording
await tui.record_start("/tmp/session.mp4", framerate=30)

# ... interact with the TUI ...

# Stop and finalize
video_path = await tui.record_stop()
```

## API Reference

### TUIDriver

| Method | Description |
|--------|-------------|
| `start()` | Start the TUI and connect to MCP server |
| `close()` | Close the TUI and clean up |
| `send(text)` | Send text (use `\n` for Enter) |
| `send_key(key)` | Send special key (`enter`, `tab`, `up`, etc.) |
| `state(format)` | Get terminal state (`"ai"`, `"full"`, `"text"`) |
| `plain_text()` | Get plain text content |
| `screenshot(path?)` | Capture PNG screenshot |
| `html_render(path?)` | Render as HTML |
| `wait_for_text(text, timeout?)` | Wait until text appears |
| `wait_for_stable(timeout?)` | Wait for output to stabilize |
| `wait_for_exit()` | Wait for process exit |
| `check_exit_status()` | Query exit status |
| `find_text(pattern, match)` | Search for text/regex |
| `find_elements(**filters)` | Find UI elements |
| `element_actions(role, text?)` | Get actions for an element |
| `diff(snapshot, chars_only?)` | Compare against snapshot |
| `annotate_element(role, row, col, ...)` | Register a custom element |
| `save_snapshot(name, type?)` | Save named snapshot |
| `assert_snapshot(name, type?)` | Compare against named snapshot |
| `record_start(path, ...)` | Start video recording |
| `record_stop()` | Stop video recording |
| `record_status()` | Check recording status |

### Supported Keys

`enter`, `tab`, `escape`, `up`, `down`, `left`, `right`, `backspace`,
`ctrl_c`, `ctrl_d`, `ctrl_z`, `page_up`, `page_down`, `home`, `end`,
`delete`

### State Formats

| Format | Model | Description |
|--------|-------|-------------|
| `"ai"` | `AIStateData` | Compact: text + highlights + summary (default) |
| `"full"` | `FullStateData` | Complete cell grid with ANSI colors |
| `"text"` | `str` | Plain text only |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint + format
ruff check tui_td/ tests/
ruff format tui_td/ tests/

# Type check (strict)
mypy tui_td/

# Install pre-commit hooks
pre-commit install
```

## Further Documentation

- [Architecture & Data Flow](docs/architecture.md) — How tui-td-py communicates with tui-td
- [API Reference](docs/api.md) — Complete methods, models, and exceptions
- [Examples](examples/) — Runnable demo scripts

## License

MIT
