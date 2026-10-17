from __future__ import annotations

from typing import Any

from candle import Candle
from strategy.decisions import (
    CloseDecision,
    EntryDecision,
    ModifyDecision,
    Position,
    PositionSide,
    StepResult,
)
from strategy.indicators import compute_indicator
from strategy.ir import StrategyDefinition


class StrategyRunError(Exception):
    pass


class StrategyRunner:
    def __init__(self, definition: StrategyDefinition) -> None:
        self._definition = definition
        self._variables: dict[str, float] = {}

    def reset(self) -> None:
        self._variables.clear()

    @property
    def variables(self) -> dict[str, float]:
        return dict(self._variables)

    def step(
        self,
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
    ) -> StepResult:
        errors: list[str] = []
        entry: EntryDecision | None = None
        modify: ModifyDecision | None = None
        close: CloseDecision | None = None

        if position is None:
            entry, phase_errors = self._run_phase(
                "entry",
                self._definition.get("entry") or [],
                candle,
                history,
                position,
            )
            errors.extend(phase_errors)
        else:
            modify, mod_errors = self._run_modify_phase(
                self._definition.get("modify") or [],
                candle,
                history,
                position,
            )
            errors.extend(mod_errors)
            close_dec, close_errors = self._run_close_phase(
                self._definition.get("close") or [],
                candle,
                history,
                position,
            )
            errors.extend(close_errors)
            close = close_dec

        return StepResult(entry=entry, modify=modify, close=close, errors=tuple(errors))

    def _run_modify_phase(
        self,
        stmts: list[dict[str, Any]],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position,
    ) -> tuple[ModifyDecision | None, list[str]]:
        sl: float | None = None
        tp: float | None = None
        errors: list[str] = []
        sl_set = False
        tp_set = False

        def on_decision(kind: str, payload: dict[str, Any]) -> bool:
            nonlocal sl, tp, sl_set, tp_set
            if kind == "set_sl" and not sl_set:
                sl = payload["value"]
                sl_set = True
                return True
            if kind == "set_tp" and not tp_set:
                tp = payload["value"]
                tp_set = True
                return True
            return False

        self._execute_stmts(stmts, candle, history, position, on_decision, errors)
        if not sl_set and not tp_set:
            return None, errors
        return ModifyDecision(sl=sl if sl_set else None, tp=tp if tp_set else None), errors

    def _run_close_phase(
        self,
        stmts: list[dict[str, Any]],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position,
    ) -> tuple[CloseDecision | None, list[str]]:
        errors: list[str] = []
        closed = False

        def on_decision(kind: str, _payload: dict[str, Any]) -> bool:
            nonlocal closed
            if kind == "close" and not closed:
                closed = True
                return True
            return False

        self._execute_stmts(stmts, candle, history, position, on_decision, errors)
        return (CloseDecision() if closed else None), errors

    def _run_phase(
        self,
        _phase: str,
        stmts: list[dict[str, Any]],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
    ) -> tuple[EntryDecision | None, list[str]]:
        errors: list[str] = []
        entry: EntryDecision | None = None

        def on_decision(kind: str, payload: dict[str, Any]) -> bool:
            nonlocal entry
            if kind == "enter" and entry is None:
                side = PositionSide(payload["side"])
                entry = EntryDecision(
                    side=side,
                    sl=float(payload["sl"]),
                    tp=float(payload["tp"]),
                )
                return True
            return False

        self._execute_stmts(stmts, candle, history, position, on_decision, errors)
        return entry, errors

    def _execute_stmts(
        self,
        stmts: list[dict[str, Any]],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
        on_decision: Any,
        errors: list[str],
    ) -> bool:
        for stmt in stmts:
            if self._execute_stmt(stmt, candle, history, position, on_decision, errors):
                return True
        return False

    def _execute_stmt(
        self,
        stmt: dict[str, Any],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
        on_decision: Any,
        errors: list[str],
    ) -> bool:
        kind = stmt.get("kind")
        try:
            if kind == "set_var":
                name = str(stmt["name"]).strip()
                value = self._eval_numeric(stmt["value"], candle, history, position)
                self._variables[name] = value
                return False
            if kind == "if":
                cond = self._eval_bool(stmt["condition"], candle, history, position)
                branch = stmt["then"] if cond else stmt.get("else") or []
                return self._execute_stmts(
                    branch, candle, history, position, on_decision, errors
                )
            if kind == "enter":
                side = stmt["side"]
                sl = self._eval_numeric(stmt["sl"], candle, history, position)
                tp = self._eval_numeric(stmt["tp"], candle, history, position)
                return on_decision("enter", {"side": side, "sl": sl, "tp": tp})
            if kind == "set_sl":
                value = self._eval_numeric(stmt["value"], candle, history, position)
                return on_decision("set_sl", {"value": value})
            if kind == "set_tp":
                value = self._eval_numeric(stmt["value"], candle, history, position)
                return on_decision("set_tp", {"value": value})
            if kind == "close":
                return on_decision("close", {})
        except StrategyRunError as exc:
            errors.append(str(exc))
            return False
        return False

    def _eval_bool(
        self,
        expr: dict[str, Any],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
    ) -> bool:
        kind = expr.get("kind")
        if kind == "compare":
            left = self._eval_numeric(expr["left"], candle, history, position)
            right = self._eval_numeric(expr["right"], candle, history, position)
            op = expr["op"]
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            raise StrategyRunError(f"unknown compare op: {op}")
        if kind == "unary" and expr.get("op") == "not":
            return not self._eval_bool(expr["operand"], candle, history, position)
        if kind == "logic":
            op = expr["op"]
            left = self._eval_bool(expr["left"], candle, history, position)
            if op == "and":
                return left and self._eval_bool(expr["right"], candle, history, position)
            if op == "or":
                return left or self._eval_bool(expr["right"], candle, history, position)
            raise StrategyRunError(f"unknown logic op: {op}")
        value = self._eval_numeric(expr, candle, history, position)
        return bool(value)

    def _eval_numeric(
        self,
        expr: dict[str, Any],
        candle: Candle,
        history: tuple[Candle, ...],
        position: Position | None,
    ) -> float:
        kind = expr.get("kind")
        if kind == "empty":
            raise StrategyRunError("incomplete expression")
        if kind == "number":
            return float(expr["value"])
        if kind == "string":
            raise StrategyRunError("string value is not numeric")
        if kind == "candle_ref":
            offset = int(expr.get("offset", 0))
            inner = expr.get("inner")
            if not isinstance(inner, dict):
                raise StrategyRunError("candle reference missing data")
            ref_candle, ref_history = self._context_at_offset(offset, candle, history)
            return self._eval_numeric(inner, ref_candle, ref_history, position)
        if kind == "indicator":
            name = str(expr.get("name", ""))
            period = int(expr.get("period", 14))
            return compute_indicator(name, period, candle, history)
        if kind == "candle_field":
            return self._candle_field(expr, candle, history)
        if kind == "variable":
            name = str(expr["name"]).strip()
            if name not in self._variables:
                raise StrategyRunError(f"undefined variable: {name}")
            return self._variables[name]
        if kind == "position_sl":
            if position is None or position.sl is None:
                raise StrategyRunError("position SL unavailable")
            return position.sl
        if kind == "position_tp":
            if position is None or position.tp is None:
                raise StrategyRunError("position TP unavailable")
            return position.tp
        if kind == "position_side":
            if position is None:
                raise StrategyRunError("position unavailable")
            return 1.0 if position.side == PositionSide.LONG else -1.0
        if kind == "binary":
            left = self._eval_numeric(expr["left"], candle, history, position)
            right = self._eval_numeric(expr["right"], candle, history, position)
            op = expr["op"]
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                if right == 0:
                    raise StrategyRunError("division by zero")
                return left / right
            raise StrategyRunError(f"unknown binary op: {op}")
        if kind == "compare":
            return 1.0 if self._eval_bool(expr, candle, history, position) else 0.0
        raise StrategyRunError(f"expression kind not numeric: {kind}")

    def _context_at_offset(
        self,
        offset: int,
        candle: Candle,
        history: tuple[Candle, ...],
    ) -> tuple[Candle, tuple[Candle, ...]]:
        series = history if history else (candle,)
        if offset >= len(series):
            raise StrategyRunError(f"candle offset {offset} out of range")
        current = series[-(offset + 1)]
        end = len(series) - offset
        sub_history = series[:end]
        return current, sub_history

    def _candle_field(
        self,
        expr: dict[str, Any],
        candle: Candle,
        history: tuple[Candle, ...],
    ) -> float:
        offset = int(expr.get("offset", 0))
        field = expr.get("field", "close")
        series = history if history else (candle,)
        if offset >= len(series):
            raise StrategyRunError(f"candle offset {offset} out of range")
        target = series[-(offset + 1)]
        value = getattr(target, field, None)
        if value is None:
            raise StrategyRunError(f"unknown candle field: {field}")
        return float(value)
