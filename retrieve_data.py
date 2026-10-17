from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from candle import (
    Candle,
    CandleError,
    Interval,
    NoCandleDataError,
    NoHigherTimeframeError,
    NoLowerTimeframeError,
)

_YF_INTERVAL: dict[Interval, str] = {
    Interval.M1: "1m",
    Interval.M5: "5m",
    Interval.M15: "15m",
    Interval.M30: "30m",
    Interval.H1: "60m",
    Interval.D1: "1d",
}

_FLOOR_RULE: dict[Interval, str] = {
    Interval.M1: "1min",
    Interval.M5: "5min",
    Interval.M15: "15min",
    Interval.M30: "30min",
    Interval.H1: "1h",
    Interval.H4: "4h",
    Interval.D1: "1D",
}


class CandleRetriever:
    def __init__(self) -> None:
        self._ticker: str | None = None
        self._start: date | datetime | None = None
        self._end: date | datetime | None = None
        self._prepost: bool = True

    def fetch(
        self,
        ticker: str,
        interval: Interval,
        start: date | datetime,
        end: date | datetime,
        *,
        prepost: bool = True,
    ) -> tuple[Candle, ...]:
        self._ticker = ticker
        self._start = start
        self._end = end
        self._prepost = prepost

        if interval is Interval.H4:
            h1 = self._rows_to_candles(self._download(Interval.H1), Interval.H1)
            candles = self._aggregate_higher(h1, Interval.H4)
        else:
            candles = self._rows_to_candles(self._download(interval), interval)

        if not candles:
            raise NoCandleDataError(ticker, interval)
        return candles

    def attach_lower(self, candles: tuple[Candle, ...]) -> None:
        self._require_fetch_context()
        if not candles:
            return
        interval = candles[0].interval
        if interval is Interval.M1:
            raise NoLowerTimeframeError(interval)
        lower_interval = interval.lower
        assert lower_interval is not None

        pending = [c for c in candles if not c.has_lower_attached()]
        if not pending:
            return

        lower_candles = self._fetch_for_range(lower_interval, pending)
        by_bucket = self._index_by_bucket(lower_candles, interval)

        for parent in pending:
            key = self._bucket_key(parent.timestamp, interval)
            children = by_bucket.get(key, ())
            if len(children) == interval.child_count:
                for child in children:
                    child.bind_higher(parent)
                parent.bind_lower(children)

    def attach_higher(self, candles: tuple[Candle, ...]) -> None:
        self._require_fetch_context()
        if not candles:
            return
        interval = candles[0].interval
        if interval is Interval.D1:
            raise NoHigherTimeframeError(interval)
        higher_interval = interval.higher
        assert higher_interval is not None

        pending = [c for c in candles if not c.has_higher_attached()]
        if not pending:
            return

        higher_candles = self._fetch_for_range(higher_interval, pending)
        higher_by_ts = {self._bucket_key(c.timestamp, higher_interval): c for c in higher_candles}
        grouped = self._group_by_bucket(pending, higher_interval)

        for bucket, members in grouped.items():
            if len(members) != higher_interval.child_count:
                continue
            parent = higher_by_ts.get(bucket)
            if parent is None:
                continue
            ordered = tuple(sorted(members, key=lambda c: c.timestamp))
            for child in ordered:
                child.bind_higher(parent)
            parent.bind_lower(ordered)

    def _require_fetch_context(self) -> None:
        if self._ticker is None:
            raise CandleError("fetch must be called before attach_lower or attach_higher")

    def _fetch_for_range(
        self, interval: Interval, candles: list[Candle]
    ) -> tuple[Candle, ...]:
        timestamps = [c.timestamp for c in candles]
        start = min(timestamps)
        end = max(timestamps)
        if interval is Interval.H4:
            h1 = self._rows_to_candles(
                self._download(Interval.H1, start=start, end=end), Interval.H1
            )
            return self._aggregate_higher(h1, Interval.H4)
        return self._rows_to_candles(self._download(interval, start=start, end=end), interval)

    def _download(
        self,
        interval: Interval,
        *,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
    ) -> pd.DataFrame:
        assert self._ticker is not None
        start = start if start is not None else self._start
        end = end if end is not None else self._end
        df = yf.download(
            tickers=self._ticker,
            start=start,
            end=end,
            interval=_YF_INTERVAL[interval],
            auto_adjust=False,
            prepost=self._prepost,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(col).lower() for col in df.columns]
        return df

    def _rows_to_candles(self, df: pd.DataFrame, interval: Interval) -> tuple[Candle, ...]:
        if df.empty:
            return ()
        candles: list[Candle] = []
        for ts, row in df.iterrows():
            candles.append(self._candle_from_row(ts, row, interval))
        return tuple(candles)

    def _candle_from_row(self, ts: Any, row: pd.Series, interval: Interval) -> Candle:
        timestamp = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        volume = row.get("volume", 0)
        if pd.isna(volume):
            volume = 0.0
        return Candle(
            timestamp=timestamp,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            adj_close=float(row["adj close"]),
            volume=float(volume),
            interval=interval,
        )

    def _aggregate_higher(
        self,
        lower_candles: tuple[Candle, ...],
        higher_interval: Interval,
    ) -> tuple[Candle, ...]:
        grouped = self._group_by_bucket(list(lower_candles), higher_interval)
        result: list[Candle] = []
        for bucket in sorted(grouped):
            members = grouped[bucket]
            if len(members) != higher_interval.child_count:
                continue
            result.append(self._compose_candle(members, bucket, higher_interval))
        return tuple(result)

    def _compose_candle(
        self, members: list[Candle], timestamp: datetime, interval: Interval
    ) -> Candle:
        ordered = sorted(members, key=lambda c: c.timestamp)
        return Candle(
            timestamp=timestamp,
            open=ordered[0].open,
            high=max(c.high for c in ordered),
            low=min(c.low for c in ordered),
            close=ordered[-1].close,
            adj_close=ordered[-1].adj_close,
            volume=sum(c.volume for c in ordered),
            interval=interval,
        )

    def _group_by_bucket(
        self, candles: list[Candle], higher_interval: Interval
    ) -> dict[datetime, list[Candle]]:
        grouped: dict[datetime, list[Candle]] = {}
        for candle in candles:
            key = self._bucket_key(candle.timestamp, higher_interval)
            grouped.setdefault(key, []).append(candle)
        return grouped

    def _index_by_bucket(
        self, candles: tuple[Candle, ...], parent_interval: Interval
    ) -> dict[datetime, tuple[Candle, ...]]:
        grouped: dict[datetime, list[Candle]] = {}
        for candle in candles:
            key = self._bucket_key(candle.timestamp, parent_interval)
            grouped.setdefault(key, []).append(candle)
        return {k: tuple(sorted(v, key=lambda c: c.timestamp)) for k, v in grouped.items()}

    def _bucket_key(self, ts: datetime, interval: Interval) -> datetime:
        floored = pd.Timestamp(ts).floor(_FLOOR_RULE[interval])
        return floored.to_pydatetime()
