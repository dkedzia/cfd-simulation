"""Expandable category catalog for algorithm building blocks."""

from __future__ import annotations

import base64

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from i18n import t
from tui.navigation import NavAction
from tui.screens.base import NavScroll
from tui.screens.strategies.algorithm_catalog import (
    CatalogEntry,
    algorithm_catalog,
    flatten_catalog,
)


def _widget_id_for_entry(entry_id: str) -> str:
    encoded = base64.urlsafe_b64encode(entry_id.encode("utf-8")).decode("ascii")
    encoded = encoded.rstrip("=").replace("-", "_")
    return f"catalog_{encoded}"


class AlgorithmCatalogScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("enter", "confirm", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._expanded: set[str] = set()
        self._index = 0
        self._roots = algorithm_catalog()
        self._selected_entry_id: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("strategy.catalog.title"), classes="title")
            yield NavScroll(id="catalog_scroll")

    def on_mount(self) -> None:
        self.focus()
        self._rebuild()

    def _scroll(self) -> NavScroll:
        return self.query_one("#catalog_scroll", NavScroll)

    def _rows(self) -> list[tuple[int, CatalogEntry, bool]]:
        return flatten_catalog(self._roots, self._expanded)

    def _items(self) -> list[NavAction]:
        return list(self._scroll().query(NavAction))

    def _label_for_row(self, depth: int, entry: CatalogEntry, is_category: bool) -> str:
        indent = "  " * depth
        if is_category:
            marker = "▼ " if entry.entry_id in self._expanded else "▶ "
            return f"{indent}{marker}{t(entry.label_key)}"
        return f"{indent}{t(entry.label_key)}"

    def _rebuild(self) -> None:
        rows = self._rows()
        if self._selected_entry_id is None and rows:
            self._selected_entry_id = rows[min(self._index, len(rows) - 1)][1].entry_id

        scroll = self._scroll()
        scroll.remove_children()

        def remount() -> None:
            current_rows = self._rows()
            for depth, entry, is_category in current_rows:
                label = self._label_for_row(depth, entry, is_category)
                scroll.mount(
                    NavAction(
                        label,
                        entry.entry_id,
                        id=_widget_id_for_entry(entry.entry_id),
                    )
                )
            if self._selected_entry_id:
                for idx, (_, entry, _) in enumerate(current_rows):
                    if entry.entry_id == self._selected_entry_id:
                        self._index = idx
                        break
            self._sync()
            self.focus()

        self.call_after_refresh(remount)

    def _sync(self) -> None:
        items = self._items()
        if not items:
            return
        self._index = max(0, min(self._index, len(items) - 1))
        rows = self._rows()
        if rows:
            self._selected_entry_id = rows[self._index][1].entry_id
        for idx, widget in enumerate(items):
            widget.set_class(idx == self._index, "nav-selected")
            widget.refresh()
        self.call_after_refresh(self._scroll_to_selection)

    def _scroll_to_selection(self) -> None:
        items = self._items()
        if not items:
            return
        selected = items[self._index]
        try:
            self._scroll().scroll_to_widget(selected, animate=False, force=True)
        except Exception:
            pass

    def action_move_up(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._sync()

    def action_move_down(self) -> None:
        items = self._items()
        if self._index < len(items) - 1:
            self._index += 1
            self._sync()

    def action_confirm(self) -> None:
        rows = self._rows()
        if not rows:
            self.dismiss(None)
            return
        _depth, entry, is_category = rows[self._index]
        self._selected_entry_id = entry.entry_id
        if is_category:
            if entry.entry_id in self._expanded:
                self._expanded.discard(entry.entry_id)
            else:
                self._expanded.add(entry.entry_id)
            self._rebuild()
            return
        self.dismiss(entry.entry_id)

    def action_cancel(self) -> None:
        self.dismiss(None)
