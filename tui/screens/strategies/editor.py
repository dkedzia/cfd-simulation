"""Visual block-tree editor for a strategy."""

from __future__ import annotations

from typing import Any

from textual import on, work
from textual.containers import Container
from textual.widgets import Static

from db.models.strategy import Strategy
from i18n import t
from strategy.ir import (
    EditorPath,
    PhaseName,
    delete_statement,
    get_statement,
    get_statement_list,
    insert_statement,
    iter_main_editor_rows,
    move_statement,
)
from strategy.validate import StrategyValidationError, phase_allows_decision, validate_definition, validate_strategy_name
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.screens.strategies.block_screens import open_block_screen
from tui.screens.strategies.path_codec import decode_path, encode_path
from tui.screens.strategies.pick_materialize import pick_and_materialize
from tui.screens.text_prompt import TextPromptScreen
from tui.widgets import ContextMenuItem


def _phase_label(phase: str) -> str:
    return t(f"strategy.phase.{phase}")


class StrategyEditorScreen(BaseScreen):
    def __init__(self, strategy: Strategy) -> None:
        super().__init__()
        self._strategy = strategy
        self._definition: dict[str, Any] = strategy.parsed_definition()
        self._status_key: str | None = None
        self._pending_focus_path: EditorPath | None = None

    def compose_body(self):
        yield Static(t("strategy.editor.title"), classes="title")
        yield nav_line("", id="strategy_name_row", enterable=True)
        yield NavAction(t("strategy.save"), "save", id="strategy_save")
        yield Static("", id="strategy_status")
        yield Container(id="strategy_tree")

    def on_mount(self) -> None:
        self._refresh_name_row()
        self._rebuild_tree()
        super().on_mount()

    def _refresh_name_row(self) -> None:
        self.query_one("#strategy_name_row", NavLine).set_label(
            f"{t('strategy.name')}: {self._strategy.name}"
        )

    def _set_status(self, key: str | None) -> None:
        self._status_key = key
        self.query_one("#strategy_status", Static).update(t(key) if key else "")

    def _rebuild_tree(self) -> None:
        tree = self.query_one("#strategy_tree", Container)
        tree.remove_children()
        self._path_by_row_id: dict[str, EditorPath] = {}
        self._add_paths: set[EditorPath] = set()
        for idx, (path, depth, label, kind) in enumerate(iter_main_editor_rows(self._definition)):
            row_id = f"editor_node_{idx}"
            self._path_by_row_id[row_id] = path
            if len(path) == 1 and path[0] in ("entry", "modify", "close") and kind == "phase":
                text = _phase_label(str(path[0]))
                tree.mount(nav_line(text, id=row_id))
            elif kind == "add":
                self._add_paths.add(path)
                tree.mount(NavAction(t("strategy.add"), f"add_{encode_path(path)}", id=row_id))
            else:
                text = f"{'  ' * depth}{label}"
                encoded = encode_path(path)
                tree.mount(NavAction(text, f"node_{encoded}", id=row_id))
        self.call_after_refresh(self._finish_rebuild)

    def _finish_rebuild(self) -> None:
        if self._pending_focus_path is not None:
            items = self._nav_items()
            target = self._pending_focus_path
            for idx, widget in enumerate(items):
                if self._path_by_row_id.get(widget.id or "") == target:
                    self._nav_index = idx
                    break
            self._pending_focus_path = None
        self._init_nav()

    def _current_phase(self, path: EditorPath) -> PhaseName:
        phase = path[0]
        assert phase in ("entry", "modify", "close")
        return phase  # type: ignore[return-value]

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if widget.id == "strategy_name_row":
            return [ContextMenuItem(t("hint.confirm"), self._edit_name)]
        if isinstance(widget, NavAction) and widget.action_id.startswith("add_"):
            raw = widget.action_id.removeprefix("add_")
            path = decode_path(raw)
            return [ContextMenuItem(t("strategy.add"), lambda p=path: self._schedule_add(p))]
        if isinstance(widget, NavAction) and widget.action_id.startswith("node_"):
            raw = widget.action_id.removeprefix("node_")
            path = decode_path(raw)
            return self._node_context_actions(path)
        return super().context_actions(widget)

    def _node_context_actions(self, path: EditorPath) -> list[ContextMenuItem]:
        actions: list[ContextMenuItem] = []
        if len(path) == 1:
            return actions

        stmt = get_statement(self._definition, path)
        kind = stmt.get("kind")
        if kind in ("if", "enter", "set_var", "set_sl", "set_tp"):
            actions.append(
                ContextMenuItem(t("strategy.open_block"), lambda p=path: self._open_block(p))
            )
        actions.append(ContextMenuItem(t("strategy.add_after"), lambda: self._schedule_add_after(path)))
        actions.append(ContextMenuItem(t("strategy.move_up"), lambda: self._move(path, -1)))
        actions.append(ContextMenuItem(t("strategy.move_down"), lambda: self._move(path, 1)))
        actions.append(ContextMenuItem(t("strategy.delete_statement"), lambda: self._delete(path)))
        return actions

    def action_nav_enter(self) -> None:
        items = self._nav_items()
        if items and not self._context_menu:
            widget = items[self._nav_index]
            if widget.id == "strategy_name_row":
                self._edit_name()
                return
            if isinstance(widget, NavAction) and widget.action_id == "save":
                self.handle_nav_save()
                return
            if isinstance(widget, NavAction) and widget.action_id.startswith("add_"):
                raw = widget.action_id.removeprefix("add_")
                self._schedule_add(decode_path(raw))
                return
        super().action_nav_enter()

    def _edit_name(self) -> None:
        def on_result(value: str | None) -> None:
            if value is None:
                return
            self._strategy.name = value.strip()
            self._refresh_name_row()

        self.app.push_screen(
            TextPromptScreen(t("strategy.name_prompt"), self._strategy.name),
            callback=on_result,
        )

    def _schedule_add(self, list_path: EditorPath) -> None:
        self.run_worker(self._add_statement(list_path), exclusive=True)

    def _schedule_add_after(self, path: EditorPath) -> None:
        self.run_worker(self._add_after(path), exclusive=True)

    async def _add_statement(self, list_path: EditorPath) -> None:
        phase = self._current_phase(list_path)
        materialized = await pick_and_materialize(self.app, phase)
        if materialized is None:
            return
        kind, payload = materialized
        if kind != "stmt":
            return
        if not phase_allows_decision(phase, str(payload.get("kind"))):
            self._set_status("strategy.error.invalid_definition")
            return
        index = len(get_statement_list(self._definition, list_path))
        self._definition = insert_statement(self._definition, list_path, index, payload)
        self._pending_focus_path = list_path + (index,)
        self._rebuild_tree()

    async def _add_after(self, path: EditorPath) -> None:
        list_path = path[:-1]
        index = path[-1]
        if not isinstance(index, int):
            return
        phase = self._current_phase(path)
        materialized = await pick_and_materialize(self.app, phase)
        if materialized is None:
            return
        kind, payload = materialized
        if kind != "stmt":
            return
        if not phase_allows_decision(phase, str(payload.get("kind"))):
            self._set_status("strategy.error.invalid_definition")
            return
        self._definition = insert_statement(self._definition, list_path, index + 1, payload)
        self._pending_focus_path = list_path + (index + 1,)
        self._rebuild_tree()

    def _delete(self, path: EditorPath) -> None:
        self._definition = delete_statement(self._definition, path)
        self._rebuild_tree()

    def _move(self, path: EditorPath, delta: int) -> None:
        self._definition = move_statement(self._definition, path, delta)
        self._rebuild_tree()

    def _open_block(self, path: EditorPath) -> None:
        def on_done(updated: dict[str, Any] | None) -> None:
            if updated is not None:
                self._definition = updated
                self._pending_focus_path = path
                self._rebuild_tree()

        open_block_screen(self.app, self._definition, path, on_done)

    def handle_nav_save(self) -> None:
        self._set_status(None)
        try:
            validate_strategy_name(self._strategy.name, exclude_id=self._strategy.id)
        except StrategyValidationError as exc:
            self._set_status(f"strategy.error.{exc.message}")
            return
        errors = validate_definition(self._definition)
        if errors:
            self._set_status("strategy.error.invalid_definition")
            return
        self._strategy.set_definition(self._definition)
        self._strategy.save()
        self._set_status("strategy.saved")

    @on(NavAction.Activated)
    def _handle_nav_action(self, event: NavAction.Activated) -> None:
        if event.action_id == "save":
            self.handle_nav_save()
            return
        if event.action_id.startswith("node_"):
            return
        handler = getattr(self, f"handle_nav_{event.action_id}", None)
        if handler is not None:
            handler()
