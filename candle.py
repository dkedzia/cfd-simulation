from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Interval(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def lower(self) -> Interval | None:
        idx = _INTERVAL_ORDER.index(self)
        return _INTERVAL_ORDER[idx - 1] if idx > 0 else None

    @property
    def higher(self) -> Interval | None:
        idx = _INTERVAL_ORDER.index(self)
        return _INTERVAL_ORDER[idx + 1] if idx < len(_INTERVAL_ORDER) - 1 else None

    @property
    def child_count(self) -> int:
        return _CHILD_COUNT[self]


_INTERVAL_ORDER: tuple[Interval, ...] = (
    Interval.M1,
    Interval.M5,
    Interval.M15,
    Interval.M30,
    Interval.H1,
    Interval.H4,
    Interval.D1,
)

_CHILD_COUNT: dict[Interval, int] = {
    Interval.M5: 5,
    Interval.M15: 3,
    Interval.M30: 2,
    Interval.H1: 2,
    Interval.H4: 4,
    Interval.D1: 6,
}


class CandleError(Exception):
    pass


class NoLowerTimeframeError(CandleError):
    def __init__(self, interval: Interval) -> None:
        super().__init__(f"{interval.value} has no lower timeframe")
        self.interval = interval


class NoHigherTimeframeError(CandleError):
    def __init__(self, interval: Interval) -> None:
        super().__init__(f"{interval.value} has no higher timeframe")
        self.interval = interval


class LowerCandlesUnavailableError(CandleError):
    def __init__(self, interval: Interval) -> None:
        super().__init__(f"Lower candles for {interval.value} are not attached")
        self.interval = interval


class HigherCandleUnavailableError(CandleError):
    def __init__(self, interval: Interval) -> None:
        super().__init__(f"Higher candle for {interval.value} is not attached")
        self.interval = interval


class NoCandleDataError(CandleError):
    def __init__(self, ticker: str, interval: Interval) -> None:
        super().__init__(f"No candle data for {ticker} at {interval.value}")
        self.ticker = ticker
        self.interval = interval


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float
    interval: Interval
    _lower: tuple[Candle, ...] = field(default=(), repr=False, compare=False)
    _higher: Candle | None = field(default=None, repr=False, compare=False)

    @property
    def lower(self) -> tuple[Candle, ...]:
        if self.interval is Interval.M1:
            raise NoLowerTimeframeError(self.interval)
        if not self._lower:
            raise LowerCandlesUnavailableError(self.interval)
        return self._lower

    @property
    def higher(self) -> Candle:
        if self.interval is Interval.D1:
            raise NoHigherTimeframeError(self.interval)
        if self._higher is None:
            raise HigherCandleUnavailableError(self.interval)
        return self._higher

    def bind_lower(self, candles: tuple[Candle, ...]) -> None:
        object.__setattr__(self, "_lower", candles)

    def bind_higher(self, parent: Candle) -> None:
        object.__setattr__(self, "_higher", parent)

    def has_lower_attached(self) -> bool:
        return bool(self._lower)

    def has_higher_attached(self) -> bool:
        return self._higher is not None
