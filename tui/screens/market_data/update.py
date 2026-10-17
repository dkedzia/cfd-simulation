"""Update an existing ticker by fetching only missing candles."""

from __future__ import annotations

from datetime import date

from textual.widgets import Static

from db.market_data import ticker_timestamp_bounds
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


def _default_update_range(ticker_id: int) -> tuple[str, str]:
    end = date.today()
    _, max_ts = ticker_timestamp_bounds(ticker_id)
    if max_ts is not None:
        start = max_ts.date()
    else:
        start = end.replace(day=1)
    return start.isoformat(), end.isoformat()


class MarketDataUpdateScreen(BaseScreen):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__()
        self._ticker = ticker
        assert ticker.id is not None
        start, end = _default_update_range(ticker.id)
        self._start = start
        self._end = end

    def compose_body(self):
        yield Static(
            t("screen.market_data.update").format(symbol=self._ticker.symbol),
            classes="title",
        )
        yield nav_line(t("market_data.update.no_overwrite"))
        min_ts, max_ts = ticker_timestamp_bounds(self._ticker.id)
        if min_ts is not None and max_ts is not None:
            yield nav_line(
                t("market_data.update.stored_range").format(
                    min=min_ts.strftime("%Y-%m-%d %H:%M"),
                    max=max_ts.strftime("%Y-%m-%d %H:%M"),
                )
            )
        yield nav_line(self._field_label("market_data.fetch.start", self._start), id="field_start", enterable=True)
        yield nav_line(self._field_label("market_data.fetch.end", self._end), id="field_end", enterable=True)
        yield NavAction(t("market_data.update.run"), "run_update", id="update_run")
        yield Static("", id="update_status")

    def _field_label(self, key: str, value: str) -> str:
        return f"{t(key)}: {value}"

    def action_nav_enter(self) -> None:
        items = self._nav_items()
        if items and not self._context_menu:
            widget = items[self._nav_index]
            if widget.id == "field_start":
                self._edit_start()
                return
            if widget.id == "field_end":
                self._edit_end()
                return
            if widget.id == "update_run":
                self.handle_nav_run_update()
                return
        super().action_nav_enter()

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if widget.id == "field_start":
            return [ContextMenuItem(t("hint.confirm"), self._edit_start)]
        if widget.id == "field_end":
            return [ContextMenuItem(t("hint.confirm"), self._edit_end)]
        return super().context_actions(widget)

    def _edit_start(self) -> None:
        self._push_prompt("market_data.fetch.start", self._start, self._set_start)

    def _edit_end(self) -> None:
        self._push_prompt("market_data.fetch.end", self._end, self._set_end)

    def _push_prompt(self, title_key: str, initial: str, setter) -> None:
        def on_result(value: str | None) -> None:
            if value is not None:
                setter(value)

        self.app.push_screen(
            TextPromptScreen(t(title_key), initial),
            callback=on_result,
        )

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
        status = self.query_one("#update_status", Static)
        status.update(message)
        self._scroll_nav_to(status)

    def handle_nav_run_update(self) -> None:
        start = _parse_date(self._start)
        end = _parse_date(self._end)
        symbol = self._ticker.symbol
        if start is None or end is None or start > end:
            self._show_status(t("market_data.fetch.invalid"))
            self.notify(t("market_data.fetch.invalid"), severity="error", timeout=4)
            return

        def on_complete(results: list[IntervalFetchResult] | None) -> None:
            if results is None:
                self._show_status(t("market_data.fetch.error"))
                self.notify(t("market_data.fetch.error"), severity="error", timeout=4)
                return
            self._show_status(t("market_data.fetch.progress.complete"))
            self.app.push_screen(MarketDataFetchReportScreen(symbol, results, update=True))

        self.app.push_screen(
            MarketDataFetchProgressScreen(
                symbol,
                start,
                end,
                title_key="market_data.fetch.progress.title_update",
            ),
            callback=on_complete,
        )
