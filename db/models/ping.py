from __future__ import annotations

from datetime import datetime, timezone

from db.active_record import ActiveRecord


class Ping(ActiveRecord):
    table = "pings"
    columns = ("id", "message", "created_at")

    message: str
    created_at: str

    def __init__(
        self,
        *,
        id: int | None = None,
        message: str = "",
        created_at: str | None = None,
    ) -> None:
        self.id = id
        self.message = message
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
