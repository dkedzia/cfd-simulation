from __future__ import annotations

import plotext as plt

from candle import Candle


def render_candlestick_chart(
    candles: list[Candle],
    *,
    width: int,
    height: int,
) -> str:
    if not candles:
        return ""
    if width < 20:
        width = 20
    if height < 8:
        height = 8

    labels = [c.timestamp.strftime("%m-%d %H:%M") for c in candles]
    opens = [c.open for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]

    plt.clf()
    plt.date_form("m-d H:M")
    data = {"Open": opens, "High": highs, "Low": lows, "Close": closes}
    plt.candlestick(labels, data)
    plt.plotsize(width, height)
    plt.theme("dark")
    return plt.build()
