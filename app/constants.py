"""Controlled vocabularies and their emoji, shared by the API, the seeders, and
(eventually) the frontend.

`Literal` is the single source of truth: the tuples below are derived from it with
`get_args`, so adding a status in one place updates validation, error messages, and
the emoji lookup together.
"""

from __future__ import annotations

import sys
from typing import Literal, get_args

# --------------------------------------------------------------------------
# vocabularies
# --------------------------------------------------------------------------
StatusLiteral = Literal["open", "in_progress", "resolved"]
STATUSES: tuple[str, ...] = get_args(StatusLiteral)

# Named severities rather than the source dataset's P1-P4: these are the values the
# AI triage step emits, and the stored value should be exactly what it returned
# rather than a translation of it. (Dataset P1-P4 can still be mapped for scoring.)
PriorityLiteral = Literal["low", "medium", "high", "critical"]
PRIORITIES: tuple[str, ...] = get_args(PriorityLiteral)

CategoryLiteral = Literal["Network", "Software", "Hardware", "Account/Access", "Billing", "Other"]
CATEGORIES: tuple[str, ...] = get_args(CategoryLiteral)

# --------------------------------------------------------------------------
# emoji
# --------------------------------------------------------------------------
# Coloured dots rather than pictographs: these render as badges in the UI, and the
# frontend reads these values from the API rather than keeping its own map.
STATUS_EMOJI: dict[str, str] = {
    "open": "🔵",
    "in_progress": "🟡",
    "resolved": "🟢",
}

PRIORITY_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

CATEGORY_EMOJI: dict[str, str] = {
    "Network": "🌐",
    "Software": "💾",
    "Hardware": "🖥️",
    "Account/Access": "🔐",
    "Billing": "💳",
    "Other": "📦",
}

# For frontend buttons/controls when a UI is built.
ACTION_EMOJI: dict[str, str] = {
    "create": "➕",
    "update": "✏️",
    "resolve": "✅",
    "reopen": "↩️",
    "search": "🔍",
    "refresh": "🔄",
    "filter": "🔽",
    "delete": "🗑️",
    "kb": "📚",
    "incident": "🎫",
    "ai": "🤖",
    "link": "🔗",
}

UNKNOWN_EMOJI = "❔"


def status_emoji(status: str | None) -> str:
    return STATUS_EMOJI.get(status or "", UNKNOWN_EMOJI)


def priority_emoji(priority: str | None) -> str:
    """Unset priority gets a neutral marker rather than a severity colour."""
    if not priority:
        return "⚪"
    return PRIORITY_EMOJI.get(priority, UNKNOWN_EMOJI)


def category_emoji(category: str | None) -> str:
    if not category:
        return "⚪"
    return CATEGORY_EMOJI.get(category, UNKNOWN_EMOJI)


def configure_console() -> None:
    """Make emoji safe to print on Windows.

    When stdout is a real console Python handles Unicode fine, but under a pipe or
    file redirect it falls back to the locale encoding (cp1252 here), and any emoji
    raises UnicodeEncodeError. Reconfiguring to UTF-8 with errors='replace' means a
    console that still can't render a glyph degrades to '?' instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # already wrapped, or not a TextIO
            pass
