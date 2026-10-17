CREATE TABLE tickers (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE candles (
    id INTEGER PRIMARY KEY,
    ticker_id INTEGER NOT NULL REFERENCES tickers (id) ON DELETE CASCADE,
    interval TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    adj_close REAL NOT NULL,
    volume REAL NOT NULL,
    UNIQUE (ticker_id, interval, timestamp)
);

CREATE INDEX idx_candles_ticker_interval_ts ON candles (ticker_id, interval, timestamp);
