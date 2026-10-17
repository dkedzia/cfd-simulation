from __future__ import annotations

from typing import Any

from strategy.ir import (
    ARITH_OPS,
    CANDLE_FIELDS,
    COMPARE_OPS,
    LOGIC_OPS,
    PhaseName,
    StrategyDefinition,
    is_decision_statement,
    statement_kinds_for_phase,
)


class StrategyValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def validate_strategy_name(name: str, *, exclude_id: int | None = None) -> None:
    from db.models.strategy import Strategy

    trimmed = name.strip()
    if not trimmed:
        raise StrategyValidationError("name_empty")
    existing = Strategy.find_by_name(trimmed)
    if existing is not None and existing.id != exclude_id:
        raise StrategyValidationError("name_taken")


def validate_definition(defn: StrategyDefinition) -> list[str]:
    errors: list[str] = []
    for phase in ("entry", "modify", "close"):
        stmts = defn.get(phase)
        if not isinstance(stmts, list):
            errors.append(f"{phase}:not_list")
            continue
        _validate_stmt_list(phase, stmts, errors, f"{phase}")
    return errors


def _validate_stmt_list(
    phase: PhaseName,
    stmts: list[Any],
    errors: list[str],
    prefix: str,
) -> None:
    allowed = set(statement_kinds_for_phase(phase))
    for idx, stmt in enumerate(stmts):
        path = f"{prefix}[{idx}]"
        if not isinstance(stmt, dict):
            errors.append(f"{path}:not_object")
            continue
        kind = stmt.get("kind")
        if kind not in allowed:
            errors.append(f"{path}:kind_not_allowed")
            continue
        if kind == "set_var":
            if not _non_empty_str(stmt.get("name")):
                errors.append(f"{path}:var_name")
            _validate_expr(stmt.get("value"), errors, f"{path}.value")
        elif kind == "if":
            _validate_expr(stmt.get("condition"), errors, f"{path}.condition", bool_context=True)
            then = stmt.get("then")
            else_ = stmt.get("else")
            if not isinstance(then, list):
                errors.append(f"{path}.then:not_list")
            else:
                _validate_stmt_list(phase, then, errors, f"{path}.then")
            if not isinstance(else_, list):
                errors.append(f"{path}.else:not_list")
            else:
                _validate_stmt_list(phase, else_, errors, f"{path}.else")
        elif kind == "enter":
            side = stmt.get("side")
            if side not in ("long", "short"):
                errors.append(f"{path}:side")
            _validate_expr(stmt.get("sl"), errors, f"{path}.sl")
            _validate_expr(stmt.get("tp"), errors, f"{path}.tp")
        elif kind in ("set_sl", "set_tp"):
            _validate_expr(stmt.get("value"), errors, f"{path}.value")
        elif kind == "close":
            pass


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_expr(
    expr: Any,
    errors: list[str],
    path: str,
    *,
    bool_context: bool = False,
) -> None:
    if not isinstance(expr, dict):
        errors.append(f"{path}:missing")
        return
    kind = expr.get("kind")
    if kind == "empty":
        errors.append(f"{path}:empty")
    elif kind == "number":
        if not isinstance(expr.get("value"), (int, float)):
            errors.append(f"{path}:number")
    elif kind == "string":
        if not isinstance(expr.get("value"), str):
            errors.append(f"{path}:string")
    elif kind == "candle_ref":
        offset = expr.get("offset")
        if not isinstance(offset, int) or offset < 0:
            errors.append(f"{path}:offset")
        _validate_expr(expr.get("inner"), errors, f"{path}.inner")
    elif kind == "indicator":
        name = expr.get("name")
        if name not in ("atr", "rsi", "ema", "vwap"):
            errors.append(f"{path}:indicator")
        period = expr.get("period")
        if not isinstance(period, int) or period <= 0:
            errors.append(f"{path}:period")
    elif kind == "candle_field":
        if expr.get("field") not in CANDLE_FIELDS:
            errors.append(f"{path}:field")
        offset = expr.get("offset")
        if not isinstance(offset, int) or offset < 0:
            errors.append(f"{path}:offset")
    elif kind == "variable":
        if not _non_empty_str(expr.get("name")):
            errors.append(f"{path}:var_name")
    elif kind in ("position_sl", "position_tp", "position_side"):
        pass
    elif kind == "binary":
        if expr.get("op") not in ARITH_OPS:
            errors.append(f"{path}:op")
        _validate_expr(expr.get("left"), errors, f"{path}.left")
        _validate_expr(expr.get("right"), errors, f"{path}.right")
    elif kind == "compare":
        if expr.get("op") not in COMPARE_OPS:
            errors.append(f"{path}:op")
        _validate_expr(expr.get("left"), errors, f"{path}.left")
        _validate_expr(expr.get("right"), errors, f"{path}.right")
    elif kind == "unary":
        if expr.get("op") != "not":
            errors.append(f"{path}:op")
        _validate_expr(expr.get("operand"), errors, f"{path}.operand", bool_context=True)
    elif kind == "logic":
        if expr.get("op") not in LOGIC_OPS:
            errors.append(f"{path}:op")
        _validate_expr(expr.get("left"), errors, f"{path}.left", bool_context=True)
        _validate_expr(expr.get("right"), errors, f"{path}.right", bool_context=True)
    else:
        errors.append(f"{path}:kind")
    if bool_context and kind in ("number", "candle_field", "variable", "binary"):
        pass


def phase_allows_decision(phase: PhaseName, kind: str) -> bool:
    if not is_decision_statement({"kind": kind}):
        return True
    return kind in statement_kinds_for_phase(phase)
