from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    entry_id: str
    label_key: str
    children: tuple[CatalogEntry, ...] = ()


def algorithm_catalog() -> tuple[CatalogEntry, ...]:
    indicators = CatalogEntry(
        "cat:indicators",
        "strategy.catalog.category.indicators",
        (
            CatalogEntry("leaf:indicator:atr", "strategy.catalog.indicator.atr"),
            CatalogEntry("leaf:indicator:rsi", "strategy.catalog.indicator.rsi"),
            CatalogEntry("leaf:indicator:ema", "strategy.catalog.indicator.ema"),
            CatalogEntry("leaf:indicator:vwap", "strategy.catalog.indicator.vwap"),
        ),
    )
    data = CatalogEntry(
        "cat:data",
        "strategy.catalog.category.data",
        (
            CatalogEntry("leaf:data:open", "strategy.catalog.data.open"),
            CatalogEntry("leaf:data:close", "strategy.catalog.data.close"),
            CatalogEntry("leaf:data:low", "strategy.catalog.data.low"),
            CatalogEntry("leaf:data:high", "strategy.catalog.data.high"),
            CatalogEntry("leaf:data:volume", "strategy.catalog.data.volume"),
            CatalogEntry("leaf:candle:prev", "strategy.catalog.candle.previous"),
            CatalogEntry("leaf:candle:earlier", "strategy.catalog.candle.earlier"),
            indicators,
        ),
    )
    conditions = CatalogEntry(
        "cat:conditions",
        "strategy.catalog.category.conditions",
        (
            CatalogEntry("leaf:stmt:if", "strategy.catalog.if"),
            CatalogEntry("leaf:stmt:if_else", "strategy.catalog.if_else"),
            CatalogEntry("leaf:expr:compare:<", "strategy.catalog.compare.lt"),
            CatalogEntry("leaf:expr:compare:<=", "strategy.catalog.compare.lte"),
            CatalogEntry("leaf:expr:compare:>", "strategy.catalog.compare.gt"),
            CatalogEntry("leaf:expr:compare:>=", "strategy.catalog.compare.gte"),
            CatalogEntry("leaf:expr:logic:and", "strategy.catalog.logic.and"),
            CatalogEntry("leaf:expr:logic:or", "strategy.catalog.logic.or"),
            CatalogEntry("leaf:expr:compare:!=", "strategy.catalog.compare.ne"),
            CatalogEntry("leaf:expr:compare:==", "strategy.catalog.compare.eq"),
        ),
    )
    variables = CatalogEntry(
        "cat:variables",
        "strategy.catalog.category.variables",
        (
            CatalogEntry("leaf:stmt:set_var", "strategy.catalog.var.assign"),
            CatalogEntry("leaf:expr:variable", "strategy.catalog.var.read"),
        ),
    )
    actions = CatalogEntry(
        "cat:actions",
        "strategy.catalog.category.actions",
        (
            CatalogEntry("leaf:stmt:set_tp", "strategy.catalog.action.set_tp"),
            CatalogEntry("leaf:stmt:set_sl", "strategy.catalog.action.set_sl"),
            CatalogEntry("leaf:stmt:enter", "strategy.catalog.action.enter"),
            CatalogEntry("leaf:stmt:close", "strategy.catalog.action.close"),
        ),
    )
    values = CatalogEntry(
        "cat:values",
        "strategy.catalog.category.values",
        (
            CatalogEntry("leaf:expr:number", "strategy.catalog.value.float"),
            CatalogEntry("leaf:expr:string", "strategy.catalog.value.string"),
        ),
    )
    return (conditions, data, variables, actions, values)


def flatten_catalog(
    roots: tuple[CatalogEntry, ...],
    expanded: set[str],
) -> list[tuple[int, CatalogEntry, bool]]:
    rows: list[tuple[int, CatalogEntry, bool]] = []

    def walk(entries: tuple[CatalogEntry, ...], depth: int) -> None:
        for entry in entries:
            is_category = bool(entry.children)
            rows.append((depth, entry, is_category))
            if is_category and entry.entry_id in expanded:
                walk(entry.children, depth + 1)

    walk(roots, 0)
    return rows
