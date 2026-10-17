"""Fetch market data from Yahoo Finance into the database."""

from __future__ import annotations

from datetime import date

from textual.widgets import Static

from db.models.ticker import Ticker
from i18n import t
from market_data.fetch import IntervalFetchResult
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.screens.market_data.fetch_progress import MarketDataFetchProgressScreen
from tui.screens.market_data.report import MarketDataFetchReportScreen
from tui.screens.text_prompt import TextPromptScreen
from tui.widgets import ContextMenuItem


def _parse_date(text: str) -> date | None:
    text = text.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class MarketDataFetchScreen(BaseScreen):
    def __init__(self) -> None:
        super().__init__()
        self._symbol = "^NDX"
        self._start = (date.today().replace(day=1)).isoformat()
        self._end = date.today().isoformat()

    def compose_body(self):
        yield Static(t("screen.market_data.fetch"), classes="title")
        yield nav_line(self._field_label("market_data.fetch.symbol", self._symbol), id="field_symbol", enterable=True)
        yield nav_line(self._field_label("market_data.fetch.start", self._start), id="field_start", enterable=True)
        yield nav_line(self._field_label("market_data.fetch.end", self._end), id="field_end", enterable=True)
        yield NavAction(t("market_data.fetch.run"), "run_fetch", id="fetch_run")
        yield Static("", id="fetch_hint")
        yield Static("", id="fetch_status")

    def _field_label(self, key: str, value: str) -> str:
        return f"{t(key)}: {value}"

    def action_nav_enter(self) -> None:
        items = self._nav_items()
        if items and not self._context_menu:
            widget = items[self._nav_index]
            if widget.id == "field_symbol":
                self._edit_symbol()
                return
            if widget.id == "field_start":
                self._edit_start()
                return
            if widget.id == "field_end":
                self._edit_end()
                return
            if widget.id == "fetch_run":
                self.handle_nav_run_fetch()
                return
        super().action_nav_enter()

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if widget.id == "field_symbol":
            return [ContextMenuItem(t("hint.confirm"), self._edit_symbol)]
        if widget.id == "field_start":
            return [ContextMenuItem(t("hint.confirm"), self._edit_start)]
        if widget.id == "field_end":
            return [ContextMenuItem(t("hint.confirm"), self._edit_end)]
        return super().context_actions(widget)

    def _push_prompt(self, title_key: str, initial: str, setter) -> None:
        def on_result(value: str | None) -> None:
            if value is not None:
                setter(value)

        self.app.push_screen(
            TextPromptScreen(t(title_key), initial),
            callback=on_result,
        )

    def _edit_symbol(self) -> None:
        self._push_prompt("market_data.fetch.symbol", self._symbol, self._set_symbol)

    def _edit_start(self) -> None:
        self._push_prompt("market_data.fetch.start", self._start, self._set_start)

    def _edit_end(self) -> None:
        self._push_prompt("market_data.fetch.end", self._end, self._set_end)

    def _set_symbol(self, value: str) -> None:
        self._symbol = value.strip()
        self.query_one("#field_symbol", NavLine).set_label(
            self._field_label("market_data.fetch.symbol", self._symbol)
        )
        self._refresh_existing_hint()

    def on_mount(self) -> None:
        super().on_mount()
        self._refresh_existing_hint()

    def _refresh_existing_hint(self) -> None:
        hint = self.query_one("#fetch_hint", Static)
        existing = Ticker.find_by_symbol(self._symbol.strip())
        if existing is not None:
            hint.update(t("market_data.fetch.existing_hint"))
        else:
            hint.update(t("market_data.fetch.no_overwrite"))

    def _set_start(self, value: str) -> None:
        self._start = value.strip()
        self.query_one("#field_start", NavLine).set_label(
            self._field_label("market_data.fetch.start", self._start)
        )

    def _set_end(self, value: str) -> None:
        self._end = value.strip()
        self.query_one("#field_end", NavLine).set_label(
            self._field_label("market_data.fetch.end", self._end)
        )

    def _show_status(self, message: str) -> None:
        status = self.query_one("#fetch_status", Static)
        status.update(message)
        self._scroll_nav_to(status)

    def handle_nav_run_fetch(self) -> None:
        start = _parse_date(self._start)
        end = _parse_date(self._end)
        symbol = self._symbol.strip()
        if not symbol or start is None or end is None or start > end:
            self._show_status(t("market_data.fetch.invalid"))
            self.notify(t("market_data.fetch.invalid"), severity="error", timeout=4)
            return

        def on_complete(results: list[IntervalFetchResult] | None) -> None:
            if results is None:
                self._show_status(t("market_data.fetch.error"))
                self.notify(t("market_data.fetch.error"), severity="error", timeout=4)
                return
            self._show_status(t("market_data.fetch.progress.complete"))
            self.app.push_screen(MarketDataFetchReportScreen(symbol, results))

        self.app.push_screen(
            MarketDataFetchProgressScreen(symbol, start, end),
            callback=on_complete,
        )
