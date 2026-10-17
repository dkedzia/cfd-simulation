"""Turn catalog leaf ids into IR statements or expressions."""

from __future__ import annotations

from typing import Any, Literal

from i18n import t
from strategy.ir import (
    default_candle_field,
    default_candle_ref,
    default_compare,
    default_indicator,
    default_logic,
    default_number,
    default_statement,
    default_string,
    default_variable,
    empty_expr,
    PhaseName,
)
from tui.screens.strategies.catalog_screen import AlgorithmCatalogScreen
from tui.screens.text_prompt import TextPromptScreen

Materialized = tuple[Literal["stmt", "expr"], dict[str, Any]]


async def pick_catalog_leaf(app) -> str | None:
    return await app.push_screen_wait(AlgorithmCatalogScreen())


async def materialize_pick(app, pick_id: str, phase: PhaseName) -> Materialized | None:
    if pick_id.startswith("leaf:stmt:"):
        kind = pick_id.removeprefix("leaf:stmt:")
        if kind == "if":
            stmt = default_statement(phase, "if")
            stmt["has_else"] = False
            return ("stmt", stmt)
        if kind == "if_else":
            stmt = default_statement(phase, "if")
            stmt["has_else"] = True
            return ("stmt", stmt)
        if kind in ("set_var", "enter", "set_sl", "set_tp", "close"):
            return ("stmt", default_statement(phase, kind))
        return None

    if pick_id.startswith("leaf:expr:compare:"):
        op = pick_id.removeprefix("leaf:expr:compare:")
        return ("expr", default_compare(op))

    if pick_id.startswith("leaf:expr:logic:"):
        op = pick_id.removeprefix("leaf:expr:logic:")
        return ("expr", default_logic(op))

    if pick_id.startswith("leaf:data:"):
        field = pick_id.removeprefix("leaf:data:")
        return ("expr", default_candle_field(field, 0))

    if pick_id == "leaf:candle:prev":
        return ("expr", default_candle_ref(1, empty_expr()))

    if pick_id == "leaf:candle:earlier":
        raw = await app.push_screen_wait(
            TextPromptScreen(t("strategy.expr.offset_prompt"), "2", select_all=True)
        )
        if raw is None:
            return None
        try:
            offset = int(raw)
        except ValueError:
            return None
        if offset < 1:
            return None
        return ("expr", default_candle_ref(offset, empty_expr()))

    if pick_id.startswith("leaf:indicator:"):
        name = pick_id.removeprefix("leaf:indicator:")
        default_period = "14" if name in ("rsi", "ema", "atr") else "1"
        raw = await app.push_screen_wait(
            TextPromptScreen(
                t("strategy.catalog.indicator.period_prompt"),
                default_period,
                select_all=True,
            )
        )
        if raw is None:
            return None
        try:
            period = int(raw)
        except ValueError:
            return None
        if period <= 0:
            return None
        if name == "vwap":
            period = 1
        return ("expr", default_indicator(name, period))

    if pick_id == "leaf:expr:variable":
        raw = await app.push_screen_wait(
            TextPromptScreen(t("strategy.expr.variable_prompt"), "var", select_all=True)
        )
        if raw is None or not raw.strip():
            return None
        return ("expr", default_variable(raw.strip()))

    if pick_id == "leaf:expr:number":
        raw = await app.push_screen_wait(
            TextPromptScreen(t("strategy.expr.number_prompt"), "0", select_all=True)
        )
        if raw is None:
            return None
        try:
            return ("expr", default_number(float(raw.replace(",", "."))))
        except ValueError:
            return None

    if pick_id == "leaf:expr:string":
        raw = await app.push_screen_wait(
            TextPromptScreen(t("strategy.catalog.value.string_prompt"), "", select_all=False)
        )
        if raw is None:
            return None
        return ("expr", default_string(raw))

    return None


async def pick_and_materialize(app, phase: PhaseName) -> Materialized | None:
    pick_id = await pick_catalog_leaf(app)
    if pick_id is None:
        return None
    return await materialize_pick(app, pick_id, phase)
