"""Base screen with shared chrome and list navigation."""

from __future__ import annotations

import logging

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from i18n import t
from tui.navigation import NavAction, NavLine, nav_line
from tui.widgets import (
    ContextMenu,
    ContextMenuItem,
    FooterBar,
    HeaderBar,
    KeyHint,
    set_footer_hints,
)

logger = logging.getLogger(__name__)


class NavScroll(VerticalScroll):
    """Body scroll area — arrows are handled by the screen, not the scroller."""

    can_focus = False
    BINDINGS: list[Binding] = []


class BaseScreen(Screen):
    """Screen with header, scrollable body, footer, and nav-item cursor."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
        Binding("up", "nav_up", "↑", show=False),
        Binding("down", "nav_down", "↓", show=False),
        Binding("enter", "nav_enter", "Enter", show=False),
    ]

    _nav_index: int = 0
    _context_menu: ContextMenu | None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._context_menu = None

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header")
        with Container(id="body"):
            with NavScroll(id="scroll_body"):
                yield from self.compose_body()
        yield FooterBar(id="footer")

    def compose_body(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.refresh_footer()
        self.call_after_refresh(self._init_nav)

    def function_keys(self) -> list[KeyHint]:
        return []

    def enter_hint_label(self) -> str:
        items = self._nav_items()
        if not items:
            return t("hint.none")
        widget = items[min(self._nav_index, len(items) - 1)]
        if isinstance(widget, NavAction):
            return t("hint.open")
        if "nav-enterable" in widget.classes:
            return t("hint.confirm")
        return t("hint.none")

    def escape_hint_label(self) -> str:
        if len(self.app.screen_stack) > 1:
            return t("hint.back")
        return t("hint.none")

    def navigation_hints(self) -> list[KeyHint]:
        return [
            KeyHint("↑↓", t("hint.select")),
            KeyHint("Enter", self.enter_hint_label()),
            KeyHint("Esc", self.escape_hint_label()),
        ]

    def refresh_footer(self) -> None:
        hints = list(self.function_keys()) + self.navigation_hints()
        set_footer_hints(self, hints)

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        actions: list[ContextMenuItem] = []
        if isinstance(widget, NavAction):
            action_id = widget.action_id
            label = getattr(widget, "_label", t("hint.run")).strip()
            actions.append(
                ContextMenuItem(
                    label,
                    lambda aid=action_id: self.post_message(NavAction.Activated(aid)),
                )
            )
        return actions

    def _close_context_menu(self) -> bool:
        menu = self._context_menu
        if menu is None:
            return False
        try:
            menu.remove()
        except Exception:
            pass
        self._context_menu = None
        self._sync_nav_highlight()
        self.refresh_footer()
        return True

    def _open_context_menu(self, anchor: NavLine, items: list[ContextMenuItem]) -> None:
        self._close_context_menu()
        menu = ContextMenu(items)
        self._context_menu = menu
        try:
            anchor.mount(menu, after=anchor)
        except Exception:
            logger.exception("Failed to mount context menu")
            self._context_menu = None
            return
        self._scroll_nav_to(menu)
        self.refresh_footer()

    def _run_context_actions(self, widget: NavLine) -> None:
        items = [a for a in self.context_actions(widget) if not a.disabled]
        if not items:
            return
        if len(items) == 1:
            items[0].callback()
            return
        self._open_context_menu(widget, list(self.context_actions(widget)))

    def _init_nav(self) -> None:
        self._close_context_menu()
        self._nav_index = 0
        self.focus()
        self._sync_nav_highlight()

    def _body(self) -> NavScroll:
        return self.query_one("#scroll_body", NavScroll)

    def _nav_items(self) -> list[NavLine]:
        return list(self._body().query(NavLine))

    def _sync_nav_highlight(self) -> None:
        items = self._nav_items()
        if not items:
            self.refresh_footer()
            return
        self._nav_index = max(0, min(self._nav_index, len(items) - 1))
        for idx, widget in enumerate(items):
            widget.set_class(idx == self._nav_index, "nav-selected")
            widget.refresh()
        self._scroll_nav_to(items[self._nav_index])
        self.refresh_footer()

    def action_nav_up(self) -> None:
        if self._context_menu is not None:
            self._context_menu.move(-1)
            self._context_menu.refresh()
            return
        items = self._nav_items()
        if not items or self._nav_index <= 0:
            return
        self._nav_index -= 1
        self._sync_nav_highlight()

    def action_nav_down(self) -> None:
        if self._context_menu is not None:
            self._context_menu.move(1)
            self._context_menu.refresh()
            return
        items = self._nav_items()
        if not items or self._nav_index >= len(items) - 1:
            return
        self._nav_index += 1
        self._sync_nav_highlight()

    def _scroll_nav_to(self, widget: Static) -> None:
        try:
            self._body().scroll_to_widget(widget, animate=False, force=True)
        except Exception:
            pass

    def action_nav_enter(self) -> None:
        if self._context_menu is not None:
            if self._context_menu.activate():
                self._close_context_menu()
            return
        items = self._nav_items()
        if not items:
            return
        self._run_context_actions(items[self._nav_index])

    @on(NavAction.Activated)
    def _handle_nav_action(self, event: NavAction.Activated) -> None:
        handler = getattr(self, f"handle_nav_{event.action_id}", None)
        if handler is not None:
            handler()

    def action_go_back(self) -> None:
        if self._close_context_menu():
            return
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
