# Changelog

All notable changes to tui-td-py will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-07

### Added

- `TUIDriver` — async context manager with 22 methods wrapping all tui-td MCP tools
- `RpcClient` — JSON-RPC 2.0 client managing subprocess lifecycle and MCP handshake
- Pydantic models: `Cell`, `Cursor`, `Size`, `AIStateData`, `FullStateData`, `TextMatch`, `Element`, `Highlight`, `DiffEntry`
- Custom exceptions: `TUITDError`, `TUIConnectionError`, `TUITimeoutError`, `TUIDriverError`
- Type aliases: `Key`, `StateFormat`, `MatchMode`, `ElementRole`, `SnapshotType`
- Lifecycle: `start()`, `close()`, async context manager (`async with`)
- Input: `send()`, `send_key()` with 18 special keys
- State queries: `state()` (ai/full/text), `plain_text()`, `screenshot()`, `html_render()`
- Wait operations: `wait_for_text()`, `wait_for_stable()`, `wait_for_exit()`
- Search: `find_text()` with partial/exact/regex match modes
- Elements: `find_elements()` with role/text/checked/disabled filters, `element_actions()`
- Diff: `diff()` for cell-level state comparison
- Snapshots: `save_snapshot()`, `assert_snapshot()`
- Annotations: `annotate_element()` for custom element registration
- Recording: `record_start()`, `record_stop()`, `record_status()`
- Exit status: `check_exit_status()`, `exit_status` property
- 46 tests (3 smoke, 5 RPC unit, 22 driver unit, 16 integration)
- 4 examples: echo_demo, basic_tui_driver, interactive_session, snapshot_diff
- 2 docs: architecture.md, api.md
- Tooling: ruff, mypy (strict), pytest, pre-commit

[0.1.0]: https://github.com/vurte/tui-td-py/releases/tag/v0.1.0
