"""Database connection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from alpha_arena.config import settings


@dataclass(frozen=True)
class DatabaseConfig:
    driver: str
    database: str


def parse_database_url(url: str) -> DatabaseConfig:
    if url.startswith("sqlite:///"):
        return DatabaseConfig(driver="sqlite", database=url[len("sqlite:///") :])
    if url.startswith("sqlite://"):
        return DatabaseConfig(driver="sqlite", database=url[len("sqlite://") :])
    raise ValueError(f"Unsupported DATABASE_URL: {url}")


def _ensure_sqlite_path(path: str) -> str:
    if path in {":memory:", ""}:
        return path
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def get_connection() -> sqlite3.Connection:
    config = parse_database_url(settings.database_url)
    if config.driver != "sqlite":
        raise ValueError("Only sqlite is supported in this runtime.")
    db_path = _ensure_sqlite_path(config.database)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
