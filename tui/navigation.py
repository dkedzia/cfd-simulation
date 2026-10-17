"""Keyboard navigation helpers for screen body lists."""

from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.widgets import Static


def _nav_text(label: str, *, selected: bool) -> Text:
    text = Text(label)
    if selected:
        text.stylize("reverse bold")
    return text


class NavLine(Static):
    """Read-only navigable row with text-only highlight."""

    DEFAULT_CLASSES = "nav-item"

    def __init__(
        self,
        text: str,
        *,
        id: str | None = None,
        enterable: bool = False,
    ) -> None:
        classes = "nav-item"
        if enterable:
            classes += " nav-enterable"
        super().__init__(id=id, classes=classes)
        self._label = text

    def set_label(self, text: str) -> None:
        self._label = text
        self.refresh()

    def render(self) -> Text:
        return _nav_text(self._label, selected=self.has_class("nav-selected"))


class NavAction(NavLine):
    """Single-line menu action triggered with Enter when highlighted."""

    class Activated(Message):
        """Posted when user confirms a NavAction row."""

        def __init__(self, action_id: str) -> None:
            super().__init__()
            self.action_id = action_id

    def __init__(self, label: str, action_id: str, *, id: str | None = None) -> None:
        super().__init__(label, id=id)
        self.action_id = action_id


def nav_line(text: str, *, id: str | None = None, enterable: bool = False) -> NavLine:
    """Read-only navigable row."""
    return NavLine(text, id=id, enterable=enterable)
