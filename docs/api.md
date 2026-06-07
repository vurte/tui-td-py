# API Reference

## TUIDriver

The main entry point. Async context manager that manages a TUI session.

```python
from tui_td import TUIDriver

async with TUIDriver("htop") as tui:
    ...
```

### Constructor

```python
TUIDriver(
    command: str,
    *,
    rows: int = 40,
    cols: int = 120,
    timeout: float = 30.0,
    chdir: str | None = None,
    executable: str = "tui-td",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | required | Shell command to run (`"htop"`, `"vim file.txt"`) |
| `rows` | `int` | `40` | Terminal height in rows |
| `cols` | `int` | `120` | Terminal width in columns |
| `timeout` | `float` | `30.0` | Default timeout for wait operations |
| `chdir` | `str \| None` | `None` | Working directory (not yet supported via MCP) |
| `executable` | `str` | `"tui-td"` | Path to tui-td binary |

### Lifecycle Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async start()` | `None` | Start the TUI and connect to MCP server |
| `async close()` | `None` | Close the TUI and clean up (idempotent) |
| `async __aenter__()` | `TUIDriver` | Context manager enter |
| `async __aexit__(...)` | `None` | Context manager exit |

### Input Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async send(text)` | `None` | Send text to the TUI (use `\n` for Enter) |
| `async send_key(key)` | `None` | Send special key (see Key type below) |

### State Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async state(format?)` | `AIStateData \| FullStateData \| str` | Get terminal state |
| `async plain_text()` | `str` | Plain text (ANSI stripped) |
| `async screenshot(path?)` | `Path` | PNG screenshot |
| `async html_render(path?)` | `str` | HTML render |

### Wait Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `async wait_for_text(text, timeout?)` | `str` | Wait until text appears |
| `async wait_for_stable(timeout?)` | `str` | Wait for output to stabilize |
| `async wait_for_exit()` | `int` | Wait for process exit, return exit code |

### Search & Elements

| Method | Returns | Description |
|--------|---------|-------------|
| `async find_text(pattern, match?)` | `list[TextMatch]` | Search for text/regex |
| `async find_elements(**filters)` | `list[Element]` | Find UI elements |
| `async element_actions(role, text?)` | `str` | Get actions for an element |

### Diff & Snapshots

| Method | Returns | Description |
|--------|---------|-------------|
| `async diff(snapshot, *, chars_only?)` | `str` | Compare against previous state |
| `async save_snapshot(name, *, type?)` | `None` | Save named snapshot to disk |
| `async assert_snapshot(name, *, type?)` | `str` | Assert current state matches snapshot |
| `async annotate_element(role, row, col, ...)` | `None` | Register custom element |

### Recording

| Method | Returns | Description |
|--------|---------|-------------|
| `async record_start(path, *, framerate?, codec?, quality?)` | `None` | Start video recording |
| `async record_stop()` | `Path` | Stop and finalize video |
| `async record_status()` | `bool` | Check if recording is active |

## Models

### Cell
```python
Cell(char: str, fg: str, bg: str, bold: bool, italic: bool, underline: bool, blink: bool)
```

### Cursor
```python
Cursor(row: int, col: int, visible: bool, style: str | int)
```

### Size
```python
Size(rows: int, cols: int)
```

### AIStateData (format="ai")
```python
AIStateData(size: Size, cursor: Cursor, text: str, highlights: list[Highlight], summary: str)
```

### FullStateData (format="full")
```python
FullStateData(size: Size, cursor: Cursor, rows: list[list[Cell]], raw: str, ...)
```

### TextMatch
```python
TextMatch(row: int, col: int, text: str, full_line: str)
```

### Element
```python
Element(role: str, text: str | None, row: int, col: int, width: int, height: int,
        checked: bool | None, focused: bool | None, disabled: bool | None, fg: str | None, bg: str | None)
```

## Exceptions

| Exception | Parent | When |
|-----------|--------|------|
| `TUITDError` | `Exception` | Base exception |
| `TUIConnectionError` | `TUITDError` | Connection/protocol errors |
| `TUITimeoutError` | `TUITDError` | Wait operations timing out |
| `TUIDriverError` | `TUITDError` | Invalid driver state |

## Type Aliases

```python
Key = Literal["enter", "tab", "escape", "up", "down", "left", "right",
              "backspace", "ctrl_c", "ctrl_d", "ctrl_z",
              "page_up", "page_down", "home", "end", "delete"]

StateFormat = Literal["ai", "full", "text"]
MatchMode = Literal["partial", "exact", "regex"]
ElementRole = Literal["button", "checkbox", "dialog", "statusbar",
                      "progress", "input", "label", "menu", "tab"]
```
