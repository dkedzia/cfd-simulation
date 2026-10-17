"""In-place editors for if/enter/value blocks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from textual.containers import Container
from textual.widgets import Static

from i18n import t
from strategy.ir import (
    EditorPath,
    ExprPath,
    delete_statement,
    empty_expr,
    get_expr_at,
    get_statement,
    get_statement_list,
    insert_statement,
    iter_expr_slot_rows,
    iter_statement_list_rows,
    move_statement,
    set_expr_at,
)
from strategy.validate import phase_allows_decision
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.screens.choice import ChoiceScreen
from tui.screens.strategies.pick_materialize import pick_and_materialize
from tui.screens.text_prompt import TextPromptScreen
from tui.widgets import ContextMenuItem


@dataclass
class _RowMeta:
    kind: str
    list_path: EditorPath | None = None
    stmt_path: EditorPath | None = None
    expr_root: str | None = None
    expr_path: ExprPath | None = None


@dataclass
class _DisplayRow:
    kind: str
    label: str
    depth: int
    list_path: EditorPath | None = None
    stmt_path: EditorPath | None = None
    expr_root: str | None = None
    expr_path: ExprPath | None = None


def _phase_from_path(path: EditorPath) -> str:
    return str(path[0])


class _BlockEditorBase(BaseScreen):
    def __init__(self, definition: dict[str, Any], stmt_path: EditorPath) -> None:
        super().__init__()
        self._definition = deepcopy(definition)
        self._stmt_path = stmt_path
        self._row_meta: dict[str, _RowMeta] = {}
        self._pending_focus_index: int | None = None

    def compose_body(self):
        yield Static(self._title(), classes="title")
        yield Container(id="block_tree")

    def _title(self) -> str:
        return t("strategy.block.title")

    def _stmt(self) -> dict[str, Any]:
        return get_statement(self._definition, self._stmt_path)

    def _apply_stmt(self, stmt: dict[str, Any]) -> None:
        lst: Any = self._definition
        for key in self._stmt_path[:-1]:
            lst = lst[key]
        idx = self._stmt_path[-1]
        assert isinstance(idx, int)
        lst[idx] = stmt

    def _row_specs(self) -> list[_DisplayRow]:
        raise NotImplementedError

    def _rebuild(self) -> None:
        tree = self.query_one("#block_tree", Container)
        tree.remove_children()
        self._row_meta.clear()
        specs = self._row_specs()
        for row_idx, spec in enumerate(specs):
            row_id = f"block_row_{row_idx}"
            self._row_meta[row_id] = _RowMeta(
                kind=spec.kind,
                list_path=spec.list_path,
                stmt_path=spec.stmt_path,
                expr_root=spec.expr_root,
                expr_path=spec.expr_path,
            )
            text = f"{'  ' * spec.depth}{spec.label}"
            if spec.kind in ("add", "expr_add"):
                tree.mount(NavAction(t("strategy.add"), f"add_{row_id}", id=row_id))
            elif spec.kind in ("slot_header",):
                tree.mount(nav_line(text, id=row_id))
            elif spec.kind == "side":
                tree.mount(nav_line(text, id=row_id, enterable=True))
            elif spec.kind == "var_name":
                tree.mount(nav_line(text, id=row_id, enterable=True))
            else:
                tree.mount(NavAction(text, f"node_{row_id}", id=row_id))
        self.call_after_refresh(self._finish_rebuild)

    def _finish_rebuild(self) -> None:
        if self._pending_focus_index is not None:
            items = self._nav_items()
            if items:
                self._nav_index = max(0, min(self._pending_focus_index, len(items) - 1))
            self._pending_focus_index = None
        self._init_nav()

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        meta = self._row_meta.get(widget.id or "")
        if not meta:
            return super().context_actions(widget)
        if meta.kind in ("add", "expr_add"):
            return [ContextMenuItem(t("strategy.add"), lambda m=meta: self._schedule_add(m))]
        return self._context_for_meta(meta)

    def _context_for_meta(self, meta: _RowMeta) -> list[ContextMenuItem]:
        actions: list[ContextMenuItem] = []
        if meta.kind == "stmt" and meta.stmt_path:
            actions.append(
                ContextMenuItem(t("strategy.delete_statement"), lambda: self._delete_stmt(meta.stmt_path))
            )
            actions.append(
                ContextMenuItem(t("strategy.move_up"), lambda: self._move_stmt(meta.stmt_path, -1))
            )
            actions.append(
                ContextMenuItem(t("strategy.move_down"), lambda: self._move_stmt(meta.stmt_path, 1))
            )
            return actions
        if meta.kind == "expr" and meta.expr_root is not None:
            stmt = self._stmt()
            root = stmt.get(meta.expr_root)
            if not isinstance(root, dict):
                root = empty_expr()
            path = meta.expr_path or ()
            node = root if not path else get_expr_at(root, path)
            if node.get("kind") == "candle_ref":
                inner = node.get("inner") or empty_expr()
                if inner.get("kind") == "empty":
                    actions.append(
                        ContextMenuItem(
                            t("strategy.pick_inner_data"),
                            lambda m=meta: self._schedule_add(
                                _RowMeta(
                                    "expr_add",
                                    expr_root=m.expr_root,
                                    expr_path=(m.expr_path or ()) + ("inner",),
                                )
                            ),
                        )
                    )
            if node.get("kind") == "indicator":
                actions.append(
                    ContextMenuItem(
                        t("strategy.edit_indicator_period"),
                        lambda m=meta: self._schedule_edit_period(m),
                    )
                )
            if node.get("kind") in ("number", "string", "variable"):
                actions.append(
                    ContextMenuItem(t("strategy.edit_slot"), lambda m=meta: self._schedule_edit_leaf(m))
                )
            actions.append(
                ContextMenuItem(t("strategy.delete_statement"), lambda m=meta: self._clear_expr(m))
            )
        return actions

    def _schedule_add(self, meta: _RowMeta) -> None:
        self.run_worker(self._on_add(meta), exclusive=True)

    def _schedule_edit_period(self, meta: _RowMeta) -> None:
        self.run_worker(self._edit_indicator_period(meta), exclusive=True)

    def _schedule_edit_leaf(self, meta: _RowMeta) -> None:
        self.run_worker(self._edit_leaf(meta), exclusive=True)

    def action_nav_enter(self) -> None:
        items = self._nav_items()
        if items and not self._context_menu:
            widget = items[self._nav_index]
            meta = self._row_meta.get(widget.id or "")
            if meta and meta.kind in ("add", "expr_add"):
                self._schedule_add(meta)
                return
        super().action_nav_enter()

    def action_go_back(self) -> None:
        if self._close_context_menu():
            return
        self.dismiss(self._definition)

    async def _on_add(self, meta: _RowMeta) -> None:
        phase = _phase_from_path(self._stmt_path)  # type: ignore[arg-type]
        materialized = await pick_and_materialize(self.app, phase)  # type: ignore[arg-type]
        if materialized is None:
            return
        kind, payload = materialized

        if meta.kind == "add" and meta.list_path is not None:
            if kind != "stmt":
                return
            if not phase_allows_decision(phase, str(payload.get("kind"))):  # type: ignore[arg-type]
                return
            index = len(get_statement_list(self._definition, meta.list_path))
            self._definition = insert_statement(self._definition, meta.list_path, index, payload)
            self._pending_focus_index = self._row_index_for_stmt(meta.list_path + (index,))
            self._rebuild()
            return

        if meta.kind == "expr_add" and meta.expr_root is not None:
            if kind != "expr":
                return
            stmt = deepcopy(self._stmt())
            expr_path = meta.expr_path or ()
            if not expr_path:
                stmt[meta.expr_root] = payload
            else:
                root = stmt.get(meta.expr_root)
                if not isinstance(root, dict):
                    root = empty_expr()
                set_expr_at(root, expr_path, payload)
                stmt[meta.expr_root] = root
            self._apply_stmt(stmt)
            self._pending_focus_index = self._row_index_for_expr(meta.expr_root, expr_path)
            self._rebuild()

    def _row_index_for_stmt(self, _path: EditorPath) -> int:
        return 0

    def _row_index_for_expr(self, _root: str, _path: ExprPath) -> int:
        return 0

    def _delete_stmt(self, path: EditorPath | None) -> None:
        if path is None:
            return
        self._definition = delete_statement(self._definition, path)
        self._rebuild()

    def _move_stmt(self, path: EditorPath | None, delta: int) -> None:
        if path is None:
            return
        self._definition = move_statement(self._definition, path, delta)
        self._rebuild()

    def _clear_expr(self, meta: _RowMeta) -> None:
        if meta.expr_root is None:
            return
        stmt = deepcopy(self._stmt())
        path = meta.expr_path or ()
        if not path:
            stmt[meta.expr_root] = empty_expr()
        else:
            root = stmt.get(meta.expr_root)
            if not isinstance(root, dict):
                root = empty_expr()
            set_expr_at(root, path, empty_expr())
            stmt[meta.expr_root] = root
        self._apply_stmt(stmt)
        self._rebuild()

    async def _edit_indicator_period(self, meta: _RowMeta) -> None:
        if meta.expr_root is None or meta.expr_path is None:
            return
        stmt = deepcopy(self._stmt())
        root = stmt[meta.expr_root]
        if not isinstance(root, dict):
            return
        node = get_expr_at(root, meta.expr_path)
        initial = str(node.get("period", 14))
        raw = await self.app.push_screen_wait(
            TextPromptScreen(
                t("strategy.catalog.indicator.period_prompt"),
                initial,
                select_all=True,
            )
        )
        if raw is None:
            return
        try:
            period = int(raw)
        except ValueError:
            return
        if period <= 0:
            return
        node = dict(node)
        node["period"] = period
        set_expr_at(root, meta.expr_path, node)
        stmt[meta.expr_root] = root
        self._apply_stmt(stmt)
        self._rebuild()

    async def _edit_leaf(self, meta: _RowMeta) -> None:
        if meta.expr_root is None or meta.expr_path is None:
            return
        stmt = deepcopy(self._stmt())
        root = stmt[meta.expr_root]
        if not isinstance(root, dict):
            return
        node = dict(get_expr_at(root, meta.expr_path))
        kind = node.get("kind")
        if kind == "number":
            raw = await self.app.push_screen_wait(
                TextPromptScreen(
                    t("strategy.expr.number_prompt"),
                    str(node.get("value", 0)),
                    select_all=True,
                )
            )
            if raw is None:
                return
            try:
                node["value"] = float(raw.replace(",", "."))
            except ValueError:
                return
        elif kind == "string":
            raw = await self.app.push_screen_wait(
                TextPromptScreen(t("strategy.catalog.value.string_prompt"), str(node.get("value", "")))
            )
            if raw is None:
                return
            node["value"] = raw
        elif kind == "variable":
            raw = await self.app.push_screen_wait(
                TextPromptScreen(
                    t("strategy.expr.variable_prompt"),
                    str(node.get("name", "var")),
                    select_all=True,
                )
            )
            if raw is None or not raw.strip():
                return
            node["name"] = raw.strip()
        set_expr_at(root, meta.expr_path, node)
        stmt[meta.expr_root] = root
        self._apply_stmt(stmt)
        self._rebuild()


def _append_expr_rows(
    rows: list[_DisplayRow],
    expr: dict[str, Any],
    expr_root: str,
    slot_label: str,
) -> None:
    for path, depth, label, kind in iter_expr_slot_rows(expr, (), 0, slot_label):
        if kind == "slot_header":
            rows.append(_DisplayRow("slot_header", label, depth))
        elif kind in ("add", "expr_add"):
            rows.append(
                _DisplayRow("expr_add", t("strategy.add"), depth, expr_root=expr_root, expr_path=path)
            )
        elif kind == "expr":
            rows.append(_DisplayRow("expr", label, depth, expr_root=expr_root, expr_path=path))


class IfBlockScreen(_BlockEditorBase):
    def _title(self) -> str:
        return t("strategy.block.if")

    def on_mount(self) -> None:
        self._rebuild()
        super().on_mount()

    def _row_specs(self) -> list[_DisplayRow]:
        stmt = self._stmt()
        rows: list[_DisplayRow] = []
        cond = stmt.get("condition") if isinstance(stmt.get("condition"), dict) else empty_expr()
        _append_expr_rows(rows, cond, "condition", t("strategy.slot.condition"))

        rows.append(_DisplayRow("slot_header", t("strategy.branch.then"), 0))
        then_path = self._stmt_path + ("then",)
        then_stmts = stmt.get("then") or []
        if not then_stmts:
            rows.append(_DisplayRow("add", t("strategy.add"), 1, list_path=then_path))
        else:
            for path, depth, label, kind in iter_statement_list_rows(then_path, then_stmts, 1):
                if kind == "add":
                    rows.append(_DisplayRow("add", t("strategy.add"), depth, list_path=path))
                else:
                    rows.append(_DisplayRow("stmt", label, depth, stmt_path=path))

        if stmt.get("has_else"):
            rows.append(_DisplayRow("slot_header", t("strategy.branch.else"), 0))
            else_path = self._stmt_path + ("else",)
            else_stmts = stmt.get("else") or []
            if not else_stmts:
                rows.append(_DisplayRow("add", t("strategy.add"), 1, list_path=else_path))
            else:
                for path, depth, label, kind in iter_statement_list_rows(else_path, else_stmts, 1):
                    if kind == "add":
                        rows.append(_DisplayRow("add", t("strategy.add"), depth, list_path=path))
                    else:
                        rows.append(_DisplayRow("stmt", label, depth, stmt_path=path))
        return rows


class EnterBlockScreen(_BlockEditorBase):
    def _title(self) -> str:
        return t("strategy.block.enter")

    def on_mount(self) -> None:
        self._rebuild()
        super().on_mount()

    def _row_specs(self) -> list[_DisplayRow]:
        stmt = self._stmt()
        rows: list[_DisplayRow] = []
        side = stmt.get("side", "long")
        rows.append(
            _DisplayRow(
                "side",
                f"{t('strategy.edit_side')}: {t(f'strategy.side.{side}')}",
                0,
            )
        )
        for root_key, slot_label in (("sl", t("strategy.slot.sl")), ("tp", t("strategy.slot.tp"))):
            expr = stmt.get(root_key) if isinstance(stmt.get(root_key), dict) else empty_expr()
            _append_expr_rows(rows, expr, root_key, slot_label)
        return rows

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        meta = self._row_meta.get(widget.id or "")
        if meta and meta.kind == "side":
            return [ContextMenuItem(t("strategy.edit_side"), self._edit_side)]
        return super().context_actions(widget)

    def _edit_side(self) -> None:
        def on_side(side: str | None) -> None:
            if side not in ("long", "short"):
                return
            stmt = deepcopy(self._stmt())
            stmt["side"] = side
            self._apply_stmt(stmt)
            self._rebuild()

        self.app.push_screen(
            ChoiceScreen(
                t("strategy.edit_side"),
                [
                    (t("strategy.side.long"), "long"),
                    (t("strategy.side.short"), "short"),
                ],
            ),
            callback=on_side,
        )


class ValueBlockScreen(_BlockEditorBase):
    def __init__(self, definition: dict[str, Any], stmt_path: EditorPath, slot_key: str) -> None:
        super().__init__(definition, stmt_path)
        self._slot_key = slot_key

    def _title(self) -> str:
        kind = str(self._stmt().get("kind", "value"))
        key = f"strategy.block.{kind}"
        from i18n import t as translate

        return translate(key) if kind in ("set_var", "set_sl", "set_tp") else translate("strategy.block.value")

    def on_mount(self) -> None:
        self._rebuild()
        super().on_mount()

    def _row_specs(self) -> list[_DisplayRow]:
        stmt = self._stmt()
        rows: list[_DisplayRow] = []
        if self._slot_key == "value" and stmt.get("kind") == "set_var":
            rows.append(_DisplayRow("slot_header", t("strategy.var.name_label"), 0))
            rows.append(_DisplayRow("var_name", str(stmt.get("name", "var")), 1))
        expr = stmt.get(self._slot_key) if isinstance(stmt.get(self._slot_key), dict) else empty_expr()
        _append_expr_rows(rows, expr, self._slot_key, t(f"strategy.slot.{self._slot_key}"))
        return rows

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        meta = self._row_meta.get(widget.id or "")
        if meta and meta.kind == "var_name":
            return [ContextMenuItem(t("strategy.edit_slot"), self._edit_var_name)]
        return super().context_actions(widget)

    def _edit_var_name(self) -> None:
        stmt = self._stmt()

        def on_result(value: str | None) -> None:
            if value is None or not value.strip():
                return
            updated = deepcopy(stmt)
            updated["name"] = value.strip()
            self._apply_stmt(updated)
            self._rebuild()

        self.app.push_screen(
            TextPromptScreen(t("strategy.expr.variable_prompt"), stmt.get("name", "var"), select_all=True),
            callback=on_result,
        )


def open_block_screen(
    app,
    definition: dict[str, Any],
    stmt_path: EditorPath,
    callback: Callable[[dict[str, Any] | None], None],
) -> None:
    stmt = get_statement(definition, stmt_path)
    kind = stmt.get("kind")
    if kind == "if":
        screen: _BlockEditorBase = IfBlockScreen(definition, stmt_path)
    elif kind == "enter":
        screen = EnterBlockScreen(definition, stmt_path)
    elif kind in ("set_var", "set_sl", "set_tp"):
        screen = ValueBlockScreen(definition, stmt_path, "value")
    elif kind == "close":
        callback(definition)
        return
    else:
        callback(None)
        return
    app.push_screen(screen, callback=callback)
