# CFD Simulation

A terminal sandbox for **trying your own CFD ideas** against historical candles.

It will not tell you what to buy, when to sell, or how to "win". You write the rules. The app walks them over stored market data so you can see what those rules would have done. Whether that is useful is up to you.

**Status: work in progress.** Simulations are still a stub. The strategy editor and market-data flow are the parts you can actually poke today. Expect rough edges, missing pieces, and breaking changes.

## What it is

- A **Textual** TUI (`python app.py`)
- Local storage of OHLCV candles (fetched through Yahoo Finance)
- A small strategy language: entry, modify, and close, with indicators, comparisons, and variables
- UI strings in English, Spanish, French, Polish, and Chinese



## What it is not

A signal service, a broker, a course, or a promise that a backtest equals live trading. Slippage, spreads, gaps, and your own mistakes are still yours.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Python 3.11+ is a reasonable baseline. macOS and Linux are what this has been developed on.

From the main menu: **Market data** to pull and browse candles, **Strategies** to build a definition, **Settings** for language. **Simulations** is a placeholder until the runner is wired into the UI.

## Contributing

PRs and issues are welcome if you feel like it. No contribution guide theater - keep changes focused, match the style around you, and add any new user-visible string through `t("dotted.key")` in all five locale files (`i18n/locales/`).

Good first targets: finish the simulation screen, tighten strategy validation, or fix something that annoyed you while using the TUI.
