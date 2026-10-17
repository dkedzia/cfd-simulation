"""Modal fetch progress with live interval updates."""

from __future__ import annotations

from datetime import date, datetime

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from db.market_data import save_ticker_candles
from i18n import t
from market_data.fetch import IntervalFetchResult, fetch_all_intervals


class MarketDataFetchProgressScreen(ModalScreen[list[IntervalFetchResult] | None]):
    """Runs fetch in a worker and shows per-interval progress."""

    DEFAULT_CSS = """
    MarketDataFetchProgressScreen {
        align: center middle;
    }
    #progress_box {
        width: 90%;
        height: auto;
        max-height: 90%;
        border: solid #808080;
        background: #1c1c1c;
        padding: 1 2;
    }
    #progress_main {
        text-style: bold;
        color: #ffffff;
        padding: 0 0 1 0;
    }
    #progress_log {
        color: #c0c0c0;
    }
    """

    def __init__(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        title_key: str = "market_data.fetch.progress.title",
    ) -> None:
        super().__init__()
        self._symbol = symbol
        self._start = start
        self._end = end
        self._title_key = title_key
        self._log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="progress_box"):
            yield Static(t(self._title_key), classes="title")
            yield Static("", id="progress_main")
            yield Static("", id="progress_log")

    def on_mount(self) -> None:
        self._set_main(t("market_data.fetch.progress.starting"))
        self.fetch_market_data()

    def _set_main(self, text: str) -> None:
        self.query_one("#progress_main", Static).update(text)

    def _append_log(self, line: str) -> None:
        self._log_lines.append(line)
        self.query_one("#progress_log", Static).update("\n".join(self._log_lines))

    def _finish(self, results: list[IntervalFetchResult]) -> None:
        self._set_main(t("market_data.fetch.progress.complete"))
        self.dismiss(results)

    def _fail(self, message: str) -> None:
        self._set_main(message)
        self.dismiss(None)

    @work(thread=True, exclusive=True)
    def fetch_market_data(self) -> None:
        try:
            end_dt = datetime.combine(self._end, datetime.max.time())
            start_dt = datetime.combine(self._start, datetime.min.time())

            def on_start(interval, idx: int, total: int) -> None:
                msg = t("market_data.fetch.progress.interval").format(
                    interval=interval.value,
                    current=idx,
                    total=total,
                    symbol=self._symbol,
                )
                self.app.call_from_thread(self._set_main, msg)

            results = fetch_all_intervals(
                self._symbol,
                start_dt,
                end_dt,
                on_interval_start=on_start,
            )

            self.app.call_from_thread(self._set_main, t("market_data.fetch.progress.saving"))
            by_interval = {r.interval: r.candles for r in results}
            _, save_stats = save_ticker_candles(self._symbol, by_interval)

            enriched: list[IntervalFetchResult] = []
            for result in results:
                stats = save_stats.get(result.interval)
                if stats is None:
                    enriched.append(result)
                    continue
                enriched_result = result.with_save_stats(stats.inserted, stats.skipped)
                enriched.append(enriched_result)
                if result.error_key and stats.fetched == 0:
                    suffix = t(result.error_key)
                    line = t("market_data.fetch.progress.line_empty").format(
                        interval=result.interval.value,
                        reason=suffix,
                    )
                else:
                    line = t("market_data.fetch.progress.line_saved").format(
                        interval=result.interval.value,
                        inserted=stats.inserted,
                        skipped=stats.skipped,
                        fetched=stats.fetched,
                    )
                self.app.call_from_thread(self._append_log, line)

            self.app.call_from_thread(self._finish, enriched)
        except Exception:
            self.app.call_from_thread(self._fail, t("market_data.fetch.error"))
