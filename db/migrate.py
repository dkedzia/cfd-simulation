from __future__ import annotations

import re
from pathlib import Path

from db.connection import connect

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_VERSION_RE = re.compile(r"^(\d{3})_")


def _ensure_schema_migrations(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY
        )
        """
    )


def _applied_versions(conn) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def _migration_files() -> list[tuple[str, Path]]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    files: list[tuple[str, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _VERSION_RE.match(path.name)
        if not match:
            continue
        files.append((match.group(1), path))
    files.sort(key=lambda item: item[0])
    return files


def migrate(db_path: Path | str | None = None) -> list[str]:
    conn = connect(db_path)
    try:
        _ensure_schema_migrations(conn)
        applied = _applied_versions(conn)
        ran: list[str] = []
        for version, path in _migration_files():
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
            conn.commit()
            ran.append(version)
        return ran
    finally:
        conn.close()
