from __future__ import annotations

from datetime import date

from candle import Candle


def _series(history: tuple[Candle, ...], candle: Candle) -> tuple[Candle, ...]:
    return history if history else (candle,)


def typical_price(c: Candle) -> float:
    return (c.high + c.low + c.close) / 3.0


def ema(values: list[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError("not enough data for EMA")
    k = 2.0 / (period + 1)
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def rsi(closes: list[float], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(closes) < period + 1:
        raise ValueError("not enough data for RSI")
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles: list[Candle], period: int) -> float:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(candles) < period + 1:
        raise ValueError("not enough data for ATR")
    trs: list[float] = []
    for i in range(1, len(candles)):
        cur = candles[i]
        prev = candles[i - 1]
        tr = max(
            cur.high - cur.low,
            abs(cur.high - prev.close),
            abs(cur.low - prev.close),
        )
        trs.append(tr)
    window = trs[-period:]
    return sum(window) / period


def session_vwap(candles: list[Candle], session_day: date) -> float:
    pv = 0.0
    vol = 0.0
    for c in candles:
        if c.timestamp.date() != session_day:
            continue
        tp = typical_price(c)
        v = float(c.volume)
        pv += tp * v
        vol += v
    if vol == 0:
        raise ValueError("no volume for session VWAP")
    return pv / vol


def compute_indicator(
    name: str,
    period: int,
    candle: Candle,
    history: tuple[Candle, ...],
) -> float:
    series = list(_series(history, candle))
    if name == "ema":
        closes = [c.close for c in series]
        return ema(closes, period)
    if name == "rsi":
        closes = [c.close for c in series]
        return rsi(closes, period)
    if name == "atr":
        return atr(series, period)
    if name == "vwap":
        return session_vwap(series, candle.timestamp.date())
    raise ValueError(f"unknown indicator: {name}")
