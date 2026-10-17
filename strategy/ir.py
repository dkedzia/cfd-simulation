from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal

PhaseName = Literal["entry", "modify", "close"]

CANDLE_FIELDS = ("open", "high", "low", "close", "volume")
COMPARE_OPS = (">", ">=", "<", "<=", "==", "!=")
ARITH_OPS = ("+", "-", "*", "/")
LOGIC_OPS = ("and", "or")


class StrategyIRError(Exception):
    pass


def default_definition() -> dict[str, Any]:
    return {"entry": [], "modify": [], "close": []}


StrategyDefinition = dict[str, Any]


def definition_to_json(defn: StrategyDefinition) -> str:
    return json.dumps(defn, ensure_ascii=False, separators=(",", ":"))


def definition_from_json(raw: str) -> StrategyDefinition:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise StrategyIRError("definition must be an object")
    for phase in ("entry", "modify", "close"):
        if phase not in data:
            data[phase] = []
    return data


def empty_expr() -> dict[str, Any]:
    return {"kind": "empty"}


def default_number(value: float = 0.0) -> dict[str, Any]:
    return {"kind": "number", "value": value}


def default_string(value: str = "") -> dict[str, Any]:
    return {"kind": "string", "value": value}


def default_candle_field(field: str = "close", offset: int = 0) -> dict[str, Any]:
    return {"kind": "candle_field", "field": field, "offset": offset}


def default_candle_ref(offset: int, inner: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "candle_ref", "offset": offset, "inner": inner}


def default_indicator(name: str, period: int = 14) -> dict[str, Any]:
    return {"kind": "indicator", "name": name, "period": period}


def default_variable(name: str = "var") -> dict[str, Any]:
    return {"kind": "variable", "name": name}


def default_statement(phase: PhaseName, kind: str) -> dict[str, Any]:
    if kind == "set_var":
        return {"kind": "set_var", "name": "var", "value": empty_expr()}
    if kind == "if":
        return {
            "kind": "if",
            "has_else": False,
            "condition": empty_expr(),
            "then": [],
            "else": [],
        }
    if kind == "enter":
        return {
            "kind": "enter",
            "side": "long",
            "sl": empty_expr(),
            "tp": empty_expr(),
        }
    if kind == "set_sl":
        return {"kind": "set_sl", "value": empty_expr()}
    if kind == "set_tp":
        return {"kind": "set_tp", "value": empty_expr()}
    if kind == "close":
        return {"kind": "close"}
    raise StrategyIRError(f"unknown statement kind: {kind}")


def default_compare(op: str = ">") -> dict[str, Any]:
    return {
        "kind": "compare",
        "op": op,
        "left": empty_expr(),
        "right": empty_expr(),
    }


def default_logic(op: str = "and") -> dict[str, Any]:
    return {
        "kind": "logic",
        "op": op,
        "left": empty_expr(),
        "right": empty_expr(),
    }


def statement_kinds_for_phase(phase: PhaseName) -> tuple[str, ...]:
    common = ("set_var", "if")
    if phase == "entry":
        return common + ("enter",)
    if phase == "modify":
        return common + ("set_sl", "set_tp")
    return common + ("close",)


def is_decision_statement(stmt: dict[str, Any]) -> bool:
    return stmt.get("kind") in ("enter", "set_sl", "set_tp", "close")


def expr_slot_paths(stmt: dict[str, Any]) -> list[tuple[str, ...]]:
    kind = stmt.get("kind")
    if kind == "set_var":
        return [("value",)]
    if kind == "if":
        return [("condition",)]
    if kind == "enter":
        return [("sl",), ("tp",)]
    if kind in ("set_sl", "set_tp"):
        return [("value",)]
    return []


def get_nested(obj: Any, path: tuple[str, ...]) -> Any:
    cur = obj
    for key in path:
        if isinstance(key, int):
            cur = cur[key]
        else:
            cur = cur[key]
    return cur


def set_nested(obj: Any, path: tuple[str, ...], value: Any) -> None:
    if not path:
        raise StrategyIRError("empty path")
    cur = obj
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def format_expression(expr: dict[str, Any] | None) -> str:
    if not expr or not isinstance(expr, dict):
        return "?"
    kind = expr.get("kind")
    if kind == "empty":
        return "…"
    if kind == "number":
        return str(expr.get("value", 0))
    if kind == "string":
        return repr(expr.get("value", ""))
    if kind == "candle_field":
        field = expr.get("field", "close")
        offset = int(expr.get("offset", 0))
        return f"candle.{field}[{offset}]"
    if kind == "candle_ref":
        offset = int(expr.get("offset", 0))
        inner = format_expression(expr.get("inner"))
        return f"candle[{offset}].{inner}"
    if kind == "indicator":
        name = str(expr.get("name", "?")).upper()
        period = int(expr.get("period", 14))
        if name == "VWAP":
            return "VWAP session"
        return f"{name} {period}"
    if kind == "variable":
        return f"${expr.get('name', '?')}"
    if kind == "position_sl":
        return "position.sl"
    if kind == "position_tp":
        return "position.tp"
    if kind == "position_side":
        return "position.side"
    if kind == "binary":
        op = expr.get("op", "+")
        left = format_expression(expr.get("left"))
        right = format_expression(expr.get("right"))
        return f"({left} {op} {right})"
    if kind == "compare":
        op = expr.get("op", ">")
        left = format_expression(expr.get("left"))
        right = format_expression(expr.get("right"))
        return f"({left} {op} {right})"
    if kind == "unary":
        op = expr.get("op", "not")
        operand = format_expression(expr.get("operand"))
        return f"({op} {operand})"
    if kind == "logic":
        op = expr.get("op", "and")
        left = format_expression(expr.get("left"))
        right = format_expression(expr.get("right"))
        return f"({left} {op} {right})"
    return "?"


def format_statement(stmt: dict[str, Any]) -> str:
    kind = stmt.get("kind", "?")
    if kind == "set_var":
        return f"set {stmt.get('name', '?')} = {format_expression(stmt.get('value'))}"
    if kind == "if":
        cond = format_expression(stmt.get("condition"))
        if stmt.get("has_else"):
            return f"if {cond} else"
        return f"if {cond}"
    if kind == "enter":
        side = stmt.get("side", "long")
        return (
            f"enter {side} sl={format_expression(stmt.get('sl'))} "
            f"tp={format_expression(stmt.get('tp'))}"
        )
    if kind == "set_sl":
        return f"set SL = {format_expression(stmt.get('value'))}"
    if kind == "set_tp":
        return f"set TP = {format_expression(stmt.get('value'))}"
    if kind == "close":
        return "close position"
    return kind


PathSegment = str | int
EditorPath = tuple[PathSegment, ...]


def get_statement_list(defn: StrategyDefinition, path: EditorPath) -> list[dict[str, Any]]:
    return _stmt_list(defn, path)


def _stmt_list(defn: StrategyDefinition, path: EditorPath) -> list[dict[str, Any]]:
    if not path:
        raise StrategyIRError("path required")
    phase = path[0]
    if phase not in ("entry", "modify", "close"):
        raise StrategyIRError("invalid phase")
    cur: Any = defn[phase]
    i = 1
    while i < len(path):
        key = path[i]
        if isinstance(key, int):
            cur = cur[key]
            i += 1
            continue
        if key in ("then", "else"):
            cur = cur[key]
            i += 1
            continue
        raise StrategyIRError(f"invalid path segment: {key}")
    if not isinstance(cur, list):
        raise StrategyIRError("path does not point to a statement list")
    return cur


def get_statement(defn: StrategyDefinition, path: EditorPath) -> dict[str, Any]:
    if len(path) < 2:
        raise StrategyIRError("statement path too short")
    lst = _stmt_list(defn, path[:-1])
    idx = path[-1]
    if not isinstance(idx, int):
        raise StrategyIRError("statement path must end with index")
    return lst[idx]


def insert_statement(
    defn: StrategyDefinition,
    list_path: EditorPath,
    index: int,
    stmt: dict[str, Any],
) -> StrategyDefinition:
    out = deepcopy(defn)
    lst = _stmt_list(out, list_path)
    lst.insert(index, stmt)
    return out


def delete_statement(defn: StrategyDefinition, path: EditorPath) -> StrategyDefinition:
    if len(path) < 2:
        raise StrategyIRError("cannot delete phase root")
    out = deepcopy(defn)
    lst = _stmt_list(out, path[:-1])
    idx = path[-1]
    if not isinstance(idx, int):
        raise StrategyIRError("invalid delete path")
    del lst[idx]
    return out


def move_statement(defn: StrategyDefinition, path: EditorPath, delta: int) -> StrategyDefinition:
    if len(path) < 2:
        raise StrategyIRError("cannot move phase root")
    out = deepcopy(defn)
    lst = _stmt_list(out, path[:-1])
    idx = path[-1]
    if not isinstance(idx, int):
        raise StrategyIRError("invalid move path")
    new_idx = idx + delta
    if new_idx < 0 or new_idx >= len(lst):
        return defn
    lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
    return out


ExprPath = tuple[str, ...]


def get_expr_at(expr: dict[str, Any], path: ExprPath) -> dict[str, Any]:
    cur: Any = expr
    for key in path:
        cur = cur[key]
    if not isinstance(cur, dict):
        raise StrategyIRError("expression path does not point to an object")
    return cur


def set_expr_at(expr: dict[str, Any], path: ExprPath, value: dict[str, Any]) -> None:
    if not path:
        raise StrategyIRError("empty expression path")
    cur: Any = expr
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def iter_statement_list_rows(
    list_path: EditorPath,
    stmts: list[dict[str, Any]],
    depth: int,
) -> list[tuple[EditorPath, int, str, str]]:
    """Rows for a statement list: statements and trailing + Add."""
    rows: list[tuple[EditorPath, int, str, str]] = []
    for idx, stmt in enumerate(stmts):
        path: EditorPath = list_path + (idx,)
        rows.append((path, depth, format_statement(stmt), "stmt"))
    rows.append((list_path, depth, "add", "add"))
    return rows


def iter_main_editor_rows(defn: StrategyDefinition) -> list[tuple[EditorPath, int, str, str]]:
    rows: list[tuple[EditorPath, int, str, str]] = []
    for phase in ("entry", "modify", "close"):
        rows.append(((phase,), 0, phase, "phase"))
        stmts = defn.get(phase) or []
        if not stmts:
            rows.append(((phase,), 1, "add", "add"))
        else:
            rows.extend(iter_statement_list_rows((phase,), stmts, 1))
    return rows


def iter_editor_rows(defn: StrategyDefinition) -> list[tuple[EditorPath, int, str]]:
    return [(p, d, label) for p, d, label, _ in iter_main_editor_rows(defn)]


def iter_expr_slot_rows(
    expr: dict[str, Any],
    base_path: ExprPath,
    depth: int,
    slot_label: str,
) -> list[tuple[ExprPath, int, str, str]]:
    """Flatten expression tree for inline editing (condition, SL, etc.)."""
    rows: list[tuple[ExprPath, int, str, str]] = []

    def walk(node: dict[str, Any], path: ExprPath, d: int) -> None:
        kind = node.get("kind")
        if kind == "empty":
            rows.append((path, d, "add", "expr_add"))
            return
        if kind in ("compare", "logic"):
            rows.append((path, d, format_expression(node), "expr"))
            walk(node.get("left") or empty_expr(), path + ("left",), d + 1)
            walk(node.get("right") or empty_expr(), path + ("right",), d + 1)
            return
        if kind == "candle_ref":
            offset = int(node.get("offset", 0))
            rows.append((path, d, f"candle_ref[{offset}]", "expr"))
            inner = node.get("inner")
            if not isinstance(inner, dict) or inner.get("kind") == "empty":
                rows.append((path + ("inner",), d + 1, "add", "expr_add"))
            else:
                walk(inner, path + ("inner",), d + 1)
            return
        rows.append((path, d, format_expression(node), "expr"))

    rows.append(((), depth, slot_label, "slot_header"))
    if not isinstance(expr, dict):
        rows.append(((), depth + 1, "add", "expr_add"))
    else:
        walk(expr, base_path, depth + 1)
    return rows
