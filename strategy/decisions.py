from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class Position:
    side: PositionSide
    sl: float | None
    tp: float | None


@dataclass(frozen=True, slots=True)
class EntryDecision:
    side: PositionSide
    sl: float
    tp: float


@dataclass(frozen=True, slots=True)
class ModifyDecision:
    sl: float | None = None
    tp: float | None = None


@dataclass(frozen=True, slots=True)
class CloseDecision:
    pass


@dataclass(frozen=True, slots=True)
class StepResult:
    entry: EntryDecision | None = None
    modify: ModifyDecision | None = None
    close: CloseDecision | None = None
    errors: tuple[str, ...] = ()
