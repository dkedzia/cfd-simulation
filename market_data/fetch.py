from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from candle import Candle, Interval, NoCandleDataError
from retrieve_data import CandleRetriever

_ALL_INTERVALS: tuple[Interval, ...] = (
    Interval.M1,
    Interval.M5,
    Interval.M15,
    Interval.M30,
    Interval.H1,
    Interval.H4,
    Interval.D1,
)


class IntervalFetchResult:
    __slots__ = ("interval", "candles", "error_key", "inserted", "skipped")

    def __init__(
        self,
        interval: Interval,
        candles: tuple[Candle, ...],
        error_key: str | None = None,
        *,
        inserted: int | None = None,
        skipped: int | None = None,
    ) -> None:
        self.interval = interval
        self.candles = candles
        self.error_key = error_key
        self.inserted = inserted
        self.skipped = skipped

    def with_save_stats(self, inserted: int, skipped: int) -> IntervalFetchResult:
        return IntervalFetchResult(
            self.interval,
            self.candles,
            self.error_key,
            inserted=inserted,
            skipped=skipped,
        )


def fetch_all_intervals(
    symbol: str,
    start: date | datetime,
    end: date | datetime,
    *,
    on_interval_start: Callable[[Interval, int, int], None] | None = None,
    on_interval_done: Callable[[IntervalFetchResult, int, int], None] | None = None,
) -> list[IntervalFetchResult]:
    retriever = CandleRetriever()
    results: list[IntervalFetchResult] = []
    total = len(_ALL_INTERVALS)
    for idx, interval in enumerate(_ALL_INTERVALS, start=1):
        if on_interval_start is not None:
            on_interval_start(interval, idx, total)
        try:
            candles = retriever.fetch(symbol, interval, start, end)
            result = IntervalFetchResult(interval, candles)
        except NoCandleDataError:
            result = IntervalFetchResult(interval, (), "market_data.fetch.empty")
        except Exception:
            result = IntervalFetchResult(interval, (), "market_data.fetch.failed")
        results.append(result)
        if on_interval_done is not None:
            on_interval_done(result, idx, total)
    return results
