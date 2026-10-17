from __future__ import annotations

from db.active_record import ActiveRecord
from strategy.ir import StrategyDefinition, default_definition, definition_from_json, definition_to_json


class Strategy(ActiveRecord):
    table = "strategies"
    columns = ("id", "name", "definition")

    name: str
    definition: str

    def __init__(
        self,
        *,
        id: int | None = None,
        name: str = "",
        definition: str | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.definition = definition if definition is not None else definition_to_json(default_definition())

    def parsed_definition(self) -> StrategyDefinition:
        return definition_from_json(self.definition)

    def set_definition(self, defn: StrategyDefinition) -> None:
        self.definition = definition_to_json(defn)

    @classmethod
    def find_by_name(cls, name: str) -> Strategy | None:
        from db.connection import connect

        conn = connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {cls.table} WHERE name = ? COLLATE NOCASE",
                (name.strip(),),
            ).fetchone()
            if row is None:
                return None
            return cls._row_to_instance(row)
        finally:
            conn.close()

    @classmethod
    def list_all(cls) -> list[Strategy]:
        from db.connection import connect

        conn = connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM {cls.table} ORDER BY name COLLATE NOCASE"
            ).fetchall()
            return [cls._row_to_instance(row) for row in rows]
        finally:
            conn.close()
