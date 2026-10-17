"""Main menu screen."""

from __future__ import annotations

from textual.widgets import Static

from i18n import t
from tui.navigation import NavAction, nav_line
from tui.screens.base import BaseScreen
from tui.screens.placeholder import PlaceholderScreen
from tui.screens.settings import SettingsScreen
from tui.widgets import KeyHint


class MainMenuScreen(BaseScreen):
    """Root menu."""

    def action_go_back(self) -> None:
        if self._close_context_menu():
            return

    def compose_body(self):
        yield Static(t("app.title"), classes="title")
        yield nav_line(t("menu.hint_select"))
        yield NavAction(t("menu.simulations"), "simulations", id="menu_simulations")
        yield NavAction(t("menu.strategies"), "strategies", id="menu_strategies")
        yield NavAction(t("menu.settings"), "settings", id="menu_settings")
        yield NavAction(t("menu.exit"), "exit", id="menu_exit")

    def enter_hint_label(self) -> str:
        items = self._nav_items()
        if items and isinstance(items[min(self._nav_index, len(items) - 1)], NavAction):
            return t("hint.open")
        return super().enter_hint_label()

    def navigation_hints(self) -> list[KeyHint]:
        return [
            KeyHint("↑↓", t("hint.select")),
            KeyHint("Enter", self.enter_hint_label()),
        ]

    def handle_nav_simulations(self) -> None:
        self.app.push_screen(PlaceholderScreen("screen.simulations"))

    def handle_nav_strategies(self) -> None:
        self.app.push_screen(PlaceholderScreen("screen.strategies"))

    def handle_nav_settings(self) -> None:
        self.app.push_screen(SettingsScreen())

    def handle_nav_exit(self) -> None:
        self.app.exit()
