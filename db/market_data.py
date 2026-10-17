from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from candle import Candle, Interval
from db.connection import connect
from db.models.ticker import Ticker


@dataclass(frozen=True, slots=True)
class IntervalSaveStats:
    fetched: int
    inserted: int
    skipped: int


def _ts_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


def save_ticker_candles(
    symbol: str,
    by_interval: dict[Interval, tuple[Candle, ...]],
) -> tuple[Ticker, dict[Interval, IntervalSaveStats]]:
    """Insert candles that are not already stored; never overwrite existing rows."""
    now = datetime.now(timezone.utc).isoformat()
    ticker = Ticker.find_by_symbol(symbol)
    if ticker is None:
        ticker = Ticker(symbol=symbol, created_at=now, fetched_at=now)
        ticker.save()
    else:
        ticker.fetched_at = now
        ticker.save()

    assert ticker.id is not None
    stats: dict[Interval, IntervalSaveStats] = {}

    conn = connect()
    try:
        for interval, candles in by_interval.items():
            fetched = len(candles)
            if fetched == 0:
                stats[interval] = IntervalSaveStats(0, 0, 0)
                continue

            rows = [
                (
                    ticker.id,
                    interval.value,
                    _ts_iso(c.timestamp),
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.adj_close,
                    c.volume,
                )
                for c in candles
            ]
            before = conn.total_changes
            conn.executemany(
                """
                INSERT INTO candles (
                    ticker_id, interval, timestamp,
                    open, high, low, close, adj_close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker_id, interval, timestamp) DO NOTHING
                """,
                rows,
            )
            inserted = conn.total_changes - before
            stats[interval] = IntervalSaveStats(
                fetched=fetched,
                inserted=inserted,
                skipped=fetched - inserted,
            )
        conn.commit()
    finally:
        conn.close()

    return ticker, stats


def upsert_ticker_and_candles(
    symbol: str,
    by_interval: dict[Interval, tuple[Candle, ...]],
) -> Ticker:
    ticker, _ = save_ticker_candles(symbol, by_interval)
    return ticker


def load_candles(
    ticker_id: int,
    interval: Interval,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Candle]:
    conn = connect()
    try:
        sql = """
            SELECT timestamp, open, high, low, close, adj_close, volume
            FROM candles
            WHERE ticker_id = ? AND interval = ?
            ORDER BY timestamp ASC
        """
        params: list = [ticker_id, interval.value]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    result: list[Candle] = []
    for row in rows:
        ts = datetime.fromisoformat(row["timestamp"])
        result.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                adj_close=float(row["adj_close"]),
                volume=float(row["volume"]),
                interval=interval,
            )
        )
    return result


def count_candles(ticker_id: int, interval: Interval) -> int:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM candles
            WHERE ticker_id = ? AND interval = ?
            """,
            (ticker_id, interval.value),
        ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


def interval_summary(ticker_id: int) -> dict[str, int]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT interval, COUNT(*) AS n
            FROM candles
            WHERE ticker_id = ?
            GROUP BY interval
            """,
            (ticker_id,),
        ).fetchall()
        return {row["interval"]: int(row["n"]) for row in rows}
    finally:
        conn.close()


def ticker_timestamp_bounds(ticker_id: int) -> tuple[datetime | None, datetime | None]:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts
            FROM candles
            WHERE ticker_id = ?
            """,
            (ticker_id,),
        ).fetchone()
        if row is None or row["min_ts"] is None:
            return None, None
        return (
            datetime.fromisoformat(row["min_ts"]),
            datetime.fromisoformat(row["max_ts"]),
        )
    finally:
        conn.close()
