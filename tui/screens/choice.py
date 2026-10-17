"""Modal list picker returning a choice id or None."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from tui.navigation import NavAction


class ChoiceScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("enter", "confirm", show=False),
    ]

    def __init__(self, title: str, choices: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._choices = choices
        self._index = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="title")
            with VerticalScroll():
                for idx, (label, choice_id) in enumerate(self._choices):
                    yield NavAction(label, choice_id, id=f"choice_{idx}")

    def on_mount(self) -> None:
        self._sync()

    def _items(self) -> list[NavAction]:
        return list(self.query(NavAction))

    def _sync(self) -> None:
        items = self._items()
        if not items:
            return
        self._index = max(0, min(self._index, len(items) - 1))
        for idx, widget in enumerate(items):
            widget.set_class(idx == self._index, "nav-selected")
            widget.refresh()

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
        items = self._items()
        if not items:
            self.dismiss(None)
            return
        self.dismiss(items[self._index].action_id)

    def action_cancel(self) -> None:
        self.dismiss(None)
