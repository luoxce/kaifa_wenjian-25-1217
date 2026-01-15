"""Simple SQL migration runner (sqlite-first)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from alpha_arena.db.connection import get_connection


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


def _ensure_schema_version(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at INTEGER NOT NULL
        );
        """
    )
    conn.commit()


def _load_migrations() -> list[Migration]:
    migrations = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        stem = path.stem
        if "_" not in stem:
            continue
        version_str, name = stem.split("_", 1)
        if not version_str.isdigit():
            continue
        migrations.append(Migration(version=int(version_str), name=name, path=path))
    return sorted(migrations, key=lambda m: m.version)


def _applied_versions(conn) -> set[int]:
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return {row["version"] for row in rows}


def migrate() -> None:
    if not MIGRATIONS_DIR.exists():
        raise FileNotFoundError(f"Missing migrations dir: {MIGRATIONS_DIR}")

    with get_connection() as conn:
        _ensure_schema_version(conn)
        applied = _applied_versions(conn)
        migrations = _load_migrations()

        for migration in migrations:
            if migration.version in applied:
                continue
            sql = migration.path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, name, applied_at) VALUES (?, ?, ?)",
                (migration.version, migration.name, int(time.time())),
            )
            conn.commit()


if __name__ == "__main__":
    migrate()
