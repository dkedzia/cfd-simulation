"""Application settings screen."""

from __future__ import annotations

from textual.widgets import Static

from i18n import SUPPORTED_LOCALES, get_locale, locale_label, save_settings, set_locale, t
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.widgets import ContextMenuItem


class SettingsScreen(BaseScreen):
    """Locale and other user preferences."""

    def __init__(self) -> None:
        super().__init__()
        self._draft_locale = get_locale()

    def _language_row_label(self) -> str:
        return f"{t('settings.language')}: {locale_label(self._draft_locale)}"

    def compose_body(self):
        yield Static(t("screen.settings"), classes="title")
        yield nav_line(
            self._language_row_label(),
            id="settings_language",
            enterable=True,
        )
        yield NavAction(t("settings.save"), "save", id="settings_save")

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if widget.id == "settings_language":
            return [
                ContextMenuItem(
                    locale_label(code),
                    lambda c=code: self._pick_locale(c),
                )
                for code in SUPPORTED_LOCALES
            ]
        return super().context_actions(widget)

    def _pick_locale(self, code: str) -> None:
        self._draft_locale = code
        row = self.query_one("#settings_language", NavLine)
        row.set_label(self._language_row_label())
        self.refresh_footer()

    def handle_nav_save(self) -> None:
        from tui.screens.main_menu import MainMenuScreen

        save_settings({"locale": self._draft_locale})
        set_locale(self._draft_locale)
        self.app.TITLE = t("app.title")
        self.app.pop_screen()
        self.app.switch_screen(MainMenuScreen())
