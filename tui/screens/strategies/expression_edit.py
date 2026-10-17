"""Replace an expression with a user-selected template."""

from __future__ import annotations

from typing import Any

from i18n import t
from strategy.ir import (
    CANDLE_FIELDS,
    default_candle_field,
    default_compare,
    default_number,
    default_variable,
)
from tui.screens.choice import ChoiceScreen
from tui.screens.text_prompt import TextPromptScreen


async def edit_expression(
    app,
    expr: dict[str, Any],
    *,
    allow_position: bool,
) -> dict[str, Any] | None:
    while True:
        choices: list[tuple[str, str]] = [
            (t("strategy.expr.number"), "number"),
            (t("strategy.expr.candle_field"), "candle_field"),
            (t("strategy.expr.variable"), "variable"),
            (t("strategy.expr.compare"), "compare"),
            (t("strategy.expr.add"), "add"),
            (t("strategy.expr.subtract"), "subtract"),
            (t("strategy.expr.and"), "and"),
            (t("strategy.expr.or"), "or"),
            (t("strategy.expr.not"), "not"),
        ]
        if allow_position:
            choices.extend(
                [
                    (t("strategy.expr.position_sl"), "position_sl"),
                    (t("strategy.expr.position_tp"), "position_tp"),
                    (t("strategy.expr.position_side"), "position_side"),
                ]
            )
        choices.append((t("strategy.expr.done"), "done"))

        picked = await app.push_screen_wait(
            ChoiceScreen(t("strategy.expr.title"), choices)
        )
        if picked is None or picked == "done":
            return expr

        if picked == "number":
            initial = "0"
            if expr.get("kind") == "number":
                initial = str(expr.get("value", 0))
            raw = await app.push_screen_wait(
                TextPromptScreen(t("strategy.expr.number_prompt"), initial)
            )
            if raw is None:
                continue
            try:
                expr = default_number(float(raw.replace(",", ".")))
            except ValueError:
                continue
            continue

        if picked == "candle_field":
            field_choice = await app.push_screen_wait(
                ChoiceScreen(
                    t("strategy.expr.candle_field"),
                    [(f, f) for f in CANDLE_FIELDS],
                )
            )
            if field_choice is None:
                continue
            offset_raw = await app.push_screen_wait(
                TextPromptScreen(t("strategy.expr.offset_prompt"), "0")
            )
            if offset_raw is None:
                continue
            try:
                offset = int(offset_raw)
            except ValueError:
                continue
            if offset < 0:
                continue
            expr = default_candle_field(field_choice, offset)
            continue

        if picked == "variable":
            raw = await app.push_screen_wait(
                TextPromptScreen(t("strategy.expr.variable_prompt"), "var")
            )
            if raw is None or not raw.strip():
                continue
            expr = default_variable(raw.strip())
            continue

        if picked in ("position_sl", "position_tp", "position_side"):
            expr = {"kind": picked}
            continue

        if picked == "compare":
            expr = default_compare()
            continue

        if picked == "add":
            expr = {
                "kind": "binary",
                "op": "+",
                "left": default_candle_field("close", 0),
                "right": default_number(0),
            }
            continue

        if picked == "subtract":
            expr = {
                "kind": "binary",
                "op": "-",
                "left": default_candle_field("close", 0),
                "right": default_number(0),
            }
            continue

        if picked == "and":
            expr = {
                "kind": "logic",
                "op": "and",
                "left": default_compare(),
                "right": default_compare(),
            }
            continue

        if picked == "or":
            expr = {
                "kind": "logic",
                "op": "or",
                "left": default_compare(),
                "right": default_compare(),
            }
            continue

        if picked == "not":
            expr = {"kind": "unary", "op": "not", "operand": default_compare()}
            continue

    return expr
