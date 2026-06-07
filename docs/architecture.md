# Architecture

## Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Python Application                    │
│                                                         │
│  async with TUIDriver("htop") as tui:                   │
│      await tui.wait_for_stable()                        │
│      state = await tui.state("ai")                      │
│      await tui.send_key("q")                            │
│                                                         │
└─────────────────────┬───────────────────────────────────┘
                      │ Python method calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   TUIDriver (driver.py)                   │
│                                                         │
│  High-level async API. Methods: send, send_key,          │
│  state, plain_text, screenshot, wait_for_text,           │
│  wait_for_stable, wait_for_exit, find_text,              │
│  find_elements, diff, snapshot, record, ...              │
│                                                         │
│  Parses responses into Pydantic models.                  │
│                                                         │
└─────────────────────┬───────────────────────────────────┘
                      │ delegates to RpcClient.call()
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    RpcClient (rpc.py)                     │
│                                                         │
│  JSON-RPC 2.0 client. Manages subprocess lifecycle:      │
│  1. Start:  tui-td serve (create_subprocess_exec)        │
│  2. Initialize: MCP handshake (initialize → initialized) │
│  3. Operational: tools/call for each method               │
│  4. Close: SIGTERM, then SIGKILL after timeout            │
│                                                         │
│  Communication: stdin/stdout, JSON-Lines                  │
│  Read loop: async task reads stdout, dispatches to       │
│             pending futures by request ID                │
│                                                         │
└─────────────────────┬───────────────────────────────────┘
                      │ stdin/stdout (JSON-RPC)
                      ▼
┌─────────────────────────────────────────────────────────┐
│               tui-td MCP Server (Ruby)                   │
│                                                         │
│  tui-td serve — reads JSON-RPC on stdin, writes to       │
│  stdout. Exposes 20+ tools: tui_start, tui_send,         │
│  tui_state, tui_screenshot, tui_find_elements, ...       │
│                                                         │
└─────────────────────┬───────────────────────────────────┘
                      │ PTY (pseudo-terminal)
                      ▼
┌─────────────────────────────────────────────────────────┐
│                 TUI Application                          │
│                                                         │
│  htop, vim, custom TUI, any terminal program             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Communication via MCP (not direct PTY)
tui-td already provides a battle-tested MCP server (`tui-td serve`) with 20+ tools.
Wrapping it via JSON-RPC over stdio is more reliable than reimplementing PTY management
and ANSI parsing in Python.

### 2. Async-first (asyncio)
The wrapper is fully async to support AI agent usage where multiple TUI sessions may
run concurrently. The subprocess and all I/O use `asyncio.create_subprocess_exec`.

### 3. No tans-parser port
tans-parser (ANSI parsing, UI element detection) runs inside tui-td's MCP server.
All structured data (state, elements, diffs) is returned pre-parsed via MCP tools.
No need for a Python port — the Pydantic models in `models.py` mirror the JSON
structures returned by the server.

### 4. Request/Response model
Each method call on `TUIDriver` translates to a single `tools/call` JSON-RPC request.
The `RpcClient._read_loop` continuously reads responses from stdout and dispatches
them to pending futures using a monotonically increasing request ID.

## Error Handling

| Layer | Error | Handling |
|-------|-------|----------|
| RpcClient.connect() | tui-td not installed | `TUIConnectionError` with install hint |
| RpcClient.connect() | MCP handshake failure | `TUIConnectionError` with protocol error |
| RpcClient.call() | Timeout | `TUIConnectionError` after `timeout` seconds |
| RpcClient.call() | Tool returns `isError: true` | `TUIConnectionError` with server error message |
| TUIDriver methods | Wrong state (e.g., send before start) | `TUIDriverError` |
| TUIDriver wait_for_* | Timeout | `TUITimeoutError` with operation name and timeout |

## Data Flow for a Typical Request

1. `await tui.state("ai")` calls `self._rpc.call("tui_state", format="ai")`
2. `RpcClient.call()` packages it as:
   ```json
   {"jsonrpc":"2.0","id":3,"method":"tools/call",
    "params":{"name":"tui_state","arguments":{"format":"ai"}}}
   ```
3. Written to subprocess stdin
4. `_read_loop` reads response from stdout:
   ```json
   {"jsonrpc":"2.0","id":3,
    "result":{"content":[{"type":"text","text":"{...state JSON...}"}]}}
   ```
5. Future resolved with result, text extracted, passed back to `state()`
6. `state()` parses JSON into `AIStateData` Pydantic model
