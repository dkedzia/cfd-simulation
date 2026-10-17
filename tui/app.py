"""CFD Simulation terminal application entry point."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from db.migrate import migrate
from i18n import init_from_settings, t
from tui.screens.base import NavScroll  # noqa: F401 — register for CSS
from tui.screens.main_menu import MainMenuScreen


class CfdApp(App):
    """Full-screen keyboard-driven CFD simulation menu."""

    CSS_PATH = Path(__file__).parent / "theme.tcss"
    TITLE = "CFD Simulation"
    ENABLE_COMMAND_PALETTE = False

    def on_mount(self) -> None:
        migrate()
        init_from_settings()
        self.TITLE = t("app.title")
        self.push_screen(MainMenuScreen())
