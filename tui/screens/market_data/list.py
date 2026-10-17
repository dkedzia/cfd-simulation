"""List stored tickers and open the browser or fetch flow."""

from __future__ import annotations

from textual import on
from textual.widgets import Static

from db.models.ticker import Ticker
from i18n import t
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.screens.market_data.browser import MarketDataBrowserScreen
from tui.screens.market_data.fetch import MarketDataFetchScreen
from tui.screens.market_data.update import MarketDataUpdateScreen
from tui.widgets import ContextMenuItem


class MarketDataListScreen(BaseScreen):
    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if isinstance(widget, NavAction) and widget.action_id.startswith("ticker_"):
            raw_id = widget.action_id.removeprefix("ticker_")
            try:
                ticker_id = int(raw_id)
            except ValueError:
                return super().context_actions(widget)

            def open_browser() -> None:
                ticker = Ticker.find(ticker_id)
                if ticker is not None:
                    self.app.push_screen(MarketDataBrowserScreen(ticker))

            def open_update() -> None:
                ticker = Ticker.find(ticker_id)
                if ticker is not None:
                    self.app.push_screen(MarketDataUpdateScreen(ticker))

            return [
                ContextMenuItem(t("market_data.open_browser"), open_browser),
                ContextMenuItem(t("market_data.update_data"), open_update),
            ]
        return super().context_actions(widget)

    def compose_body(self):
        yield Static(t("screen.market_data"), classes="title")
        yield nav_line(t("menu.hint_select"))
        yield NavAction(t("market_data.fetch_new"), "fetch_new", id="md_fetch_new")
        for ticker in Ticker.list_all():
            label = f"{ticker.symbol} — {t('market_data.ticker_fetched_at')}: {ticker.fetched_at[:19]}"
            yield NavAction(label, f"ticker_{ticker.id}", id=f"md_ticker_{ticker.id}")

    @on(NavAction.Activated)
    def _handle_nav_action(self, event: NavAction.Activated) -> None:
        if event.action_id == "fetch_new":
            self.handle_nav_fetch_new()
            return
        if event.action_id.startswith("ticker_"):
            return
        handler = getattr(self, f"handle_nav_{event.action_id}", None)
        if handler is not None:
            handler()

    def handle_nav_fetch_new(self) -> None:
        self.app.push_screen(MarketDataFetchScreen())
