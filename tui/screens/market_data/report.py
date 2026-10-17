"""Summary after a market data fetch."""

from __future__ import annotations

from textual.widgets import Static

from i18n import t
from market_data.fetch import IntervalFetchResult
from tui.navigation import NavAction, nav_line
from tui.screens.base import BaseScreen


class MarketDataFetchReportScreen(BaseScreen):
    def __init__(
        self,
        symbol: str,
        results: list[IntervalFetchResult],
        *,
        update: bool = False,
    ) -> None:
        super().__init__()
        self._symbol = symbol
        self._results = results
        self._update = update

    def compose_body(self):
        title = (
            t("market_data.report.title_update")
            if self._update
            else t("market_data.report.title")
        )
        yield Static(title, classes="title")
        yield nav_line(f"{t('market_data.fetch.symbol')}: {self._symbol}")
        for result in self._results:
            line = self._interval_line(result)
            yield nav_line(line)
        yield NavAction(t("nav.back"), "back", id="report_back")

    def _interval_line(self, result: IntervalFetchResult) -> str:
        name = result.interval.value
        count = len(result.candles)
        if result.error_key and count == 0:
            return f"{name}: 0 ({t(result.error_key)})"
        if result.inserted is not None and result.skipped is not None:
            return t("market_data.report.line_saved").format(
                interval=name,
                inserted=result.inserted,
                skipped=result.skipped,
                fetched=count,
            )
        return f"{name}: {count}"

    def handle_nav_back(self) -> None:
        self.app.pop_screen()
