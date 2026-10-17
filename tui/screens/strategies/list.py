"""List saved strategies."""

from __future__ import annotations

from textual import on
from textual.widgets import Static

from db.models.strategy import Strategy
from i18n import t
from strategy.ir import default_definition
from tui.navigation import NavAction, NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.screens.strategies.editor import StrategyEditorScreen
from tui.widgets import ContextMenuItem


class StrategyListScreen(BaseScreen):
    def compose_body(self):
        yield Static(t("screen.strategies"), classes="title")
        yield nav_line(t("menu.hint_select"))
        yield NavAction(t("strategy.new"), "new", id="strategy_new")
        for strategy in Strategy.list_all():
            yield NavAction(strategy.name, f"open_{strategy.id}", id=f"strategy_{strategy.id}")

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if isinstance(widget, NavAction) and widget.action_id.startswith("open_"):
            raw = widget.action_id.removeprefix("open_")
            try:
                strategy_id = int(raw)
            except ValueError:
                return super().context_actions(widget)

            def open_editor() -> None:
                record = Strategy.find(strategy_id)
                if record is not None:
                    self.app.push_screen(StrategyEditorScreen(record))

            def delete_strategy() -> None:
                record = Strategy.find(strategy_id)
                if record is not None:
                    record.delete()
                    self._reload_strategies()

            return [
                ContextMenuItem(t("hint.open"), open_editor),
                ContextMenuItem(t("strategy.delete"), delete_strategy),
            ]
        return super().context_actions(widget)

    @on(NavAction.Activated)
    def _handle_nav_action(self, event: NavAction.Activated) -> None:
        if event.action_id == "new":
            self.handle_nav_new()
            return
        if event.action_id.startswith("open_"):
            return
        handler = getattr(self, f"handle_nav_{event.action_id}", None)
        if handler is not None:
            handler()

    def handle_nav_new(self) -> None:
        record = Strategy(name=t("strategy.default_name"))
        record.set_definition(default_definition())
        self.app.push_screen(StrategyEditorScreen(record))

    def _reload_strategies(self) -> None:
        body = self._body()
        for widget in list(body.query(NavAction)):
            if widget.action_id.startswith("open_"):
                widget.remove()
        for strategy in Strategy.list_all():
            body.mount(
                NavAction(
                    strategy.name,
                    f"open_{strategy.id}",
                    id=f"strategy_{strategy.id}",
                )
            )
        self.call_after_refresh(self._init_nav)
