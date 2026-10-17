"""Browse stored candles: chart, table, and single-candle detail."""

from __future__ import annotations

from enum import Enum

from textual.binding import Binding
from textual.widgets import Static

from candle import Candle, Interval
from db.market_data import load_candles
from db.models.ticker import Ticker
from i18n import t
from tui.charts.candlestick import render_candlestick_chart
from tui.navigation import NavLine, nav_line
from tui.screens.base import BaseScreen
from tui.widgets import ContextMenuItem, KeyHint

_INTERVALS: tuple[Interval, ...] = (
    Interval.M1,
    Interval.M5,
    Interval.M15,
    Interval.M30,
    Interval.H1,
    Interval.H4,
    Interval.D1,
)

_CHART_WINDOW = 48
_TABLE_PAGE = 20


class ViewMode(str, Enum):
    CHART = "chart"
    TABLE = "table"
    DETAIL = "detail"


class MarketDataBrowserScreen(BaseScreen):
    BINDINGS = BaseScreen.BINDINGS + [
        Binding("left", "scroll_prev", "Prev", show=False),
        Binding("right", "scroll_next", "Next", show=False),
    ]

    def __init__(self, ticker: Ticker) -> None:
        super().__init__()
        self._ticker = ticker
        self._interval = Interval.M5
        self._view = ViewMode.CHART
        self._candles: list[Candle] = []
        self._offset = 0
        self._detail_index = 0

    def compose_body(self):
        yield Static(
            f"{t('screen.market_data.browser')}: {self._ticker.symbol}",
            classes="title",
        )
        yield nav_line(self._interval_label(), id="md_interval", enterable=True)
        yield nav_line(self._view_label(), id="md_view", enterable=True)
        yield Static("", id="md_content")

    def on_mount(self) -> None:
        super().on_mount()
        self._reload_candles()

    def _interval_label(self) -> str:
        return f"{t('market_data.browser.interval')}: {self._interval.value}"

    def _view_label(self) -> str:
        key = {
            ViewMode.CHART: "market_data.view.chart",
            ViewMode.TABLE: "market_data.view.table",
            ViewMode.DETAIL: "market_data.view.detail",
        }[self._view]
        return f"{t('market_data.browser.view')}: {t(key)}"

    def context_actions(self, widget: NavLine) -> list[ContextMenuItem]:
        if widget.id == "md_interval":
            return [
                ContextMenuItem(
                    iv.value,
                    lambda i=iv: self._set_interval(i),
                )
                for iv in _INTERVALS
            ]
        if widget.id == "md_view":
            return [
                ContextMenuItem(t("market_data.view.chart"), lambda: self._set_view(ViewMode.CHART)),
                ContextMenuItem(t("market_data.view.table"), lambda: self._set_view(ViewMode.TABLE)),
                ContextMenuItem(t("market_data.view.detail"), lambda: self._set_view(ViewMode.DETAIL)),
            ]
        return super().context_actions(widget)

    def _set_interval(self, interval: Interval) -> None:
        self._interval = interval
        self.query_one("#md_interval", NavLine).set_label(self._interval_label())
        self._reload_candles()

    def _set_view(self, view: ViewMode) -> None:
        self._view = view
        self.query_one("#md_view", NavLine).set_label(self._view_label())
        self._offset = 0
        self._detail_index = 0
        self._refresh_content()

    def _reload_candles(self) -> None:
        assert self._ticker.id is not None
        self._candles = load_candles(self._ticker.id, self._interval)
        self._offset = max(0, len(self._candles) - _CHART_WINDOW)
        self._detail_index = max(0, len(self._candles) - 1)
        self._refresh_content()

    def _refresh_content(self) -> None:
        widget = self.query_one("#md_content", Static)
        if not self._candles:
            widget.update(t("market_data.no_data"))
            self.refresh_footer()
            return
        if self._view is ViewMode.CHART:
            widget.update(self._render_chart())
        elif self._view is ViewMode.TABLE:
            widget.update(self._render_table())
        else:
            widget.update(self._render_detail())
        self.refresh_footer()

    def _visible_slice(self, size: int) -> list[Candle]:
        if not self._candles:
            return []
        end = min(self._offset + size, len(self._candles))
        start = max(0, end - size)
        self._offset = start
        return self._candles[start:end]

    def _render_chart(self) -> str:
        chunk = self._visible_slice(_CHART_WINDOW)
        size = self.size
        width = max(40, (size.width or 80) - 4)
        height = max(12, (size.height or 24) - 12)
        chart = render_candlestick_chart(chunk, width=width, height=height)
        header = t("market_data.chart.range").format(
            start=self._offset + 1,
            end=self._offset + len(chunk),
            total=len(self._candles),
        )
        return f"{header}\n{chart}"

    def _render_table(self) -> str:
        chunk = self._visible_slice(_TABLE_PAGE)
        lines = [
            f"{t('market_data.table.header')}",
            "─" * 72,
        ]
        for idx, c in enumerate(chunk, start=self._offset + 1):
            ts = c.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"{idx:>5} {ts}  O:{c.open:.2f} H:{c.high:.2f} "
                f"L:{c.low:.2f} C:{c.close:.2f} A:{c.adj_close:.2f} V:{c.volume:.0f}"
            )
        lines.append(
            t("market_data.table.range").format(
                start=self._offset + 1,
                end=self._offset + len(chunk),
                total=len(self._candles),
            )
        )
        return "\n".join(lines)

    def _render_detail(self) -> str:
        if not self._candles:
            return t("market_data.no_data")
        self._detail_index = max(0, min(self._detail_index, len(self._candles) - 1))
        c = self._candles[self._detail_index]
        ts = c.timestamp.isoformat()
        return "\n".join(
            [
                t("market_data.detail.position").format(
                    current=self._detail_index + 1,
                    total=len(self._candles),
                ),
                f"{t('market_data.detail.timestamp')}: {ts}",
                f"{t('market_data.detail.open')}: {c.open:.4f}",
                f"{t('market_data.detail.high')}: {c.high:.4f}",
                f"{t('market_data.detail.low')}: {c.low:.4f}",
                f"{t('market_data.detail.close')}: {c.close:.4f}",
                f"{t('market_data.detail.adj_close')}: {c.adj_close:.4f}",
                f"{t('market_data.detail.volume')}: {c.volume:.0f}",
            ]
        )

    def function_keys(self) -> list[KeyHint]:
        if self._view is ViewMode.DETAIL and self._candles:
            return [
                KeyHint("←→", t("market_data.hint.candle")),
            ]
        if self._view in (ViewMode.CHART, ViewMode.TABLE) and self._candles:
            return [
                KeyHint("←→", t("market_data.hint.scroll")),
            ]
        return []

    def action_scroll_prev(self) -> None:
        if not self._candles:
            return
        if self._view is ViewMode.DETAIL:
            if self._detail_index > 0:
                self._detail_index -= 1
                self._refresh_content()
            return
        step = _CHART_WINDOW if self._view is ViewMode.CHART else _TABLE_PAGE
        self._offset = max(0, self._offset - step)
        self._refresh_content()

    def action_scroll_next(self) -> None:
        if not self._candles:
            return
        if self._view is ViewMode.DETAIL:
            if self._detail_index < len(self._candles) - 1:
                self._detail_index += 1
                self._refresh_content()
            return
        step = _CHART_WINDOW if self._view is ViewMode.CHART else _TABLE_PAGE
        window = _CHART_WINDOW if self._view is ViewMode.CHART else _TABLE_PAGE
        max_offset = max(0, len(self._candles) - window)
        self._offset = min(max_offset, self._offset + step)
        self._refresh_content()
