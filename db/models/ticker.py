from __future__ import annotations

from datetime import datetime, timezone

from db.active_record import ActiveRecord


class Ticker(ActiveRecord):
    table = "tickers"
    columns = ("id", "symbol", "created_at", "fetched_at")

    symbol: str
    created_at: str
    fetched_at: str

    def __init__(
        self,
        *,
        id: int | None = None,
        symbol: str = "",
        created_at: str | None = None,
        fetched_at: str | None = None,
    ) -> None:
        self.id = id
        self.symbol = symbol
        now = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now
        self.fetched_at = fetched_at or now

    @classmethod
    def find_by_symbol(cls, symbol: str) -> Ticker | None:
        from db.connection import connect

        conn = connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {cls.table} WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            if row is None:
                return None
            return cls._row_to_instance(row)
        finally:
            conn.close()

    @classmethod
    def list_all(cls) -> list[Ticker]:
        from db.connection import connect

        conn = connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM {cls.table} ORDER BY symbol COLLATE NOCASE"
            ).fetchall()
            return [cls._row_to_instance(row) for row in rows]
        finally:
            conn.close()
