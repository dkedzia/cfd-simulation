"""Empty section screens with Back navigation."""

from __future__ import annotations

from textual.widgets import Static

from i18n import t
from tui.navigation import NavAction
from tui.screens.base import BaseScreen


class PlaceholderScreen(BaseScreen):
    """Minimal screen reserved for future content."""

    def __init__(self, title_key: str) -> None:
        super().__init__()
        self._title_key = title_key

    def compose_body(self):
        yield Static(t(self._title_key), classes="title")
        yield NavAction(t("nav.back"), "back", id="nav_back")

    def handle_nav_back(self) -> None:
        self.app.pop_screen()
