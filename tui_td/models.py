"""Pydantic models and type aliases for tui-td-py.

Maps 1:1 to the structured data returned by the tui-td MCP server.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Type Aliases ──────────────────────────────────────────────

Key = Literal[
    "enter",
    "tab",
    "escape",
    "up",
    "down",
    "left",
    "right",
    "backspace",
    "ctrl_c",
    "ctrl_d",
    "ctrl_z",
    "page_up",
    "page_down",
    "home",
    "end",
    "delete",
]

StateFormat = Literal["ai", "full", "text"]
MatchMode = Literal["partial", "exact", "regex"]
ElementRole = Literal[
    "button",
    "checkbox",
    "dialog",
    "statusbar",
    "progress",
    "input",
    "label",
    "menu",
    "tab",
]
SnapshotType = Literal["text", "full", "png", "html", "all"]

# ── Cell-level Models ─────────────────────────────────────────


class Cell(BaseModel):
    """A single character cell in the terminal grid."""

    char: str
    fg: str = "default"
    bg: str = "default"
    bold: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False


class Cursor(BaseModel):
    """Cursor position and style."""

    row: int
    col: int
    visible: bool = True
    style: str | int = "block"  # DECSCUSR values: 0=default, 1=blinking block, etc.


class Size(BaseModel):
    """Terminal dimensions."""

    rows: int
    cols: int


# ── State Models ──────────────────────────────────────────────


class Highlight(BaseModel):
    """A highlighted/styled text segment (from ai-format)."""

    row: int
    text: str
    bold: bool = False
    fg: str | None = None
    bg: str | None = None


class AIStateData(BaseModel):
    """AI-friendly compact terminal state (format='ai')."""

    size: Size
    cursor: Cursor
    text: str
    highlights: list[Highlight] = Field(default_factory=list)
    summary: str = ""


class FullStateData(BaseModel):
    """Full terminal state with cell grid (format='full')."""

    size: Size
    cursor: Cursor
    cursor_visible: bool = True
    cursor_style: str | int = "block"
    mouse_mode: Any | None = None
    mouse_format: Any | None = None
    rows: list[list[Cell]]
    raw: str = ""


# ── Search / Element Models ───────────────────────────────────


class TextMatch(BaseModel):
    """A text search result from find_text()."""

    row: int
    col: int
    text: str
    full_line: str


class Element(BaseModel):
    """A detected UI element from find_elements()."""

    role: ElementRole
    text: str | None = None
    row: int
    col: int
    width: int = 1
    height: int = 1
    checked: bool | None = None
    focused: bool | None = None
    disabled: bool | None = None
    fg: str | None = None
    bg: str | None = None


# ── Diff Models ───────────────────────────────────────────────


class CellDiff(BaseModel):
    """A single cell difference from diff()."""

    before: Cell
    after: Cell


class DiffEntry(BaseModel):
    """A cell-level difference entry from diff()."""

    row: int
    col: int
    before: Cell
    after: Cell
