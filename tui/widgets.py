"""Shared chrome widgets: header, footer, context menu."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from i18n import t
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeyHint:
    """Footer function key description."""

    key: str
    label: str
    disabled: bool = False


@dataclass(frozen=True)
class ContextMenuItem:
    """One entry in an inline row context menu."""

    label: str
    callback: Callable[[], None]
    disabled: bool = False


class ContextMenu(Static):
    """Compact action list mounted directly under a nav row."""

    DEFAULT_CLASSES = "context-menu"

    def __init__(self, items: list[ContextMenuItem], *, id: str = "context_menu") -> None:
        super().__init__(id=id, classes="context-menu")
        self._items = list(items)
        self._index = 0
        self._ensure_enabled_index()

    def _enabled_indices(self) -> list[int]:
        return [i for i, item in enumerate(self._items) if not item.disabled]

    def _ensure_enabled_index(self) -> None:
        enabled = self._enabled_indices()
        if not enabled:
            self._index = 0
            return
        if self._index not in enabled:
            self._index = enabled[0]

    def move(self, delta: int) -> None:
        enabled = self._enabled_indices()
        if not enabled:
            return
        try:
            pos = enabled.index(self._index)
        except ValueError:
            pos = 0
        pos = (pos + delta) % len(enabled)
        self._index = enabled[pos]

    def activate(self) -> bool:
        if not self._items or self._items[self._index].disabled:
            return False
        self._items[self._index].callback()
        return True

    def render(self) -> Text:
        text = Text()
        for idx, item in enumerate(self._items):
            if idx:
                text.append("\n")
            prefix = "► " if idx == self._index else "  "
            if item.disabled:
                text.append(prefix + item.label, style="dim")
            elif idx == self._index:
                text.append(prefix + item.label, style="reverse bold")
            else:
                text.append(prefix + item.label)
        return text


class HeaderBar(Static):
    """Top bar with app title and clock."""

    clock_text: reactive[str] = reactive("00:00:00")

    def on_mount(self) -> None:
        self.set_interval(1, self._tick_clock)
        self._tick_clock()

    def _tick_clock(self) -> None:
        self.clock_text = datetime.now().strftime("%H:%M:%S")

    def render(self) -> Text:
        title = getattr(self.app, "TITLE", t("app.title"))
        line = Text()
        line.append(str(title), style="bold")
        width = self.size.width or 80
        right = Text(self.clock_text, style="bold")
        pad = width - len(line.plain) - len(right.plain)
        if pad > 1:
            line.append(" " * pad)
        line.append_text(right)
        return line


class FooterBar(Static):
    """Bottom bar showing active screen function keys."""

    hints: reactive[list[KeyHint]] = reactive(list)

    def watch_hints(self) -> None:
        self.refresh()

    @staticmethod
    def _format_hints(hints: list[KeyHint]) -> Text:
        line = Text()
        for idx, hint in enumerate(hints):
            if idx:
                line.append("  ")
            if hint.disabled:
                line.append(hint.key, style="dim")
                line.append(f" {hint.label}", style="dim")
            else:
                line.append(hint.key, style="bold white on rgb(74,74,74)")
                line.append(f" {hint.label}")
        return line

    def render(self) -> Text:
        try:
            hints = list(self.hints)
            nav_start = next((i for i, h in enumerate(hints) if h.key == "↑↓"), len(hints))
            actions = hints[:nav_start]
            nav = hints[nav_start:]
            text = self._format_hints(actions)
            if nav:
                text.append("\n")
                text.append_text(self._format_hints(nav))
            return text
        except Exception as exc:
            logger.exception("FooterBar render failed: %s", exc)
            return Text(" ")


def set_footer_hints(widget: Widget, hints: list[KeyHint]) -> None:
    """Update footer on the active screen."""
    try:
        screen = widget.app.screen
        footer = screen.query_one(FooterBar)
    except Exception:
        return
    footer.hints = hints
