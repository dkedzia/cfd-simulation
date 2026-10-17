from __future__ import annotations

from typing import Any, ClassVar, Self

from db.connection import connect


class ActiveRecord:
    table: ClassVar[str]
    columns: ClassVar[tuple[str, ...]]

    id: int | None = None

    def __init__(self, **kwargs: Any) -> None:
        for col in self.columns:
            if col in kwargs:
                setattr(self, col, kwargs[col])

    @classmethod
    def _row_to_instance(cls, row) -> Self:
        data = {col: row[col] for col in cls.columns if col in row.keys()}
        return cls(**data)

    @classmethod
    def find(cls, record_id: int) -> Self | None:
        conn = connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {cls.table} WHERE id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                return None
            return cls._row_to_instance(row)
        finally:
            conn.close()

    @classmethod
    def all(cls) -> list[Self]:
        conn = connect()
        try:
            rows = conn.execute(f"SELECT * FROM {cls.table}").fetchall()
            return [cls._row_to_instance(row) for row in rows]
        finally:
            conn.close()

    def save(self) -> Self:
        conn = connect()
        try:
            if self.id is None:
                cols = [c for c in self.columns if c != "id"]
                placeholders = ", ".join("?" for _ in cols)
                names = ", ".join(cols)
                values = [getattr(self, c) for c in cols]
                cur = conn.execute(
                    f"INSERT INTO {self.table} ({names}) VALUES ({placeholders})",
                    values,
                )
                self.id = cur.lastrowid
            else:
                cols = [c for c in self.columns if c != "id"]
                assignments = ", ".join(f"{c} = ?" for c in cols)
                values = [getattr(self, c) for c in cols]
                values.append(self.id)
                conn.execute(
                    f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                    values,
                )
            conn.commit()
            return self
        finally:
            conn.close()

    def delete(self) -> None:
        if self.id is None:
            return
        conn = connect()
        try:
            conn.execute(
                f"DELETE FROM {self.table} WHERE id = ?",
                (self.id,),
            )
            conn.commit()
            self.id = None
        finally:
            conn.close()
