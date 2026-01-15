"""Read-only data service for market data access."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from alpha_arena.config import settings
from alpha_arena.data.models import FundingSnapshot, MarketSnapshot, PriceSnapshot


MARKET_DATA_MAPPING = {
    "timestamp": ("timestamp", "ts", "time", "t"),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c", "last"),
    "volume": ("volume", "vol", "base_volume", "v"),
}

FUNDING_MAPPING = {
    "timestamp": ("timestamp", "ts", "time"),
    "funding_rate": ("funding_rate", "rate", "funding"),
    "next_funding_time": ("next_funding_time", "next_time", "next_ts"),
}

PRICE_MAPPING = {
    "timestamp": ("timestamp", "ts", "time"),
    "last": ("last", "last_price", "trade_price"),
    "mark": ("mark", "mark_price"),
    "index": ("index", "index_price"),
}


def _parse_sqlite_path(database_url: str) -> str:
    if not database_url.startswith("sqlite://"):
        raise ValueError(f"Only sqlite is supported, got: {database_url}")
    path = database_url[len("sqlite://") :]
    if path.startswith("//"):
        path = path[1:]
    elif path.startswith("/"):
        path = path[1:]
    if not path:
        raise ValueError(f"Invalid sqlite path in DATABASE_URL: {database_url}")
    return _resolve_db_path(path)


def _resolve_db_path(path: str) -> str:
    if path in {":memory:", ""}:
        return path
    candidate = Path(path)
    if not candidate.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        project_candidate = project_root / candidate
        cwd_candidate = Path.cwd() / candidate
        if project_candidate.exists():
            candidate = project_candidate
        elif cwd_candidate.exists():
            candidate = cwd_candidate
        else:
            candidate = project_candidate
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return str(candidate)


class DataService:
    """Unified read-only access layer for market data."""

    def __init__(self, db_path: Optional[str] = None, database_url: Optional[str] = None):
        resolved_url = database_url or settings.database_url
        if db_path:
            self.db_path = _resolve_db_path(db_path)
        else:
            self.db_path = _parse_sqlite_path(resolved_url)
        self._column_cache: dict[str, dict[str, Optional[str]]] = {}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_table_columns(self, conn: sqlite3.Connection, table: str) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row["name"] for row in rows]

    def _map_columns(
        self,
        conn: sqlite3.Connection,
        table: str,
        mapping: dict[str, Iterable[str]],
        required: Iterable[str],
    ) -> dict[str, Optional[str]]:
        if table in self._column_cache:
            return self._column_cache[table]

        columns = self._get_table_columns(conn, table)
        if not columns:
            raise ValueError(f"Table {table} not found in database: {self.db_path}")

        lower_map = {col.lower(): col for col in columns}
        resolved: dict[str, Optional[str]] = {}

        for standard, candidates in mapping.items():
            actual = None
            for candidate in candidates:
                candidate_lower = candidate.lower()
                if candidate_lower in lower_map:
                    actual = lower_map[candidate_lower]
                    break
            if actual is None and standard in required:
                raise ValueError(
                    f"{table} missing required column for {standard}. "
                    f"Columns={columns}"
                )
            resolved[standard] = actual

        self._column_cache[table] = resolved
        return resolved

    def list_symbols(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM market_data ORDER BY symbol"
            ).fetchall()
        return [row["symbol"] for row in rows]

    def list_timeframes(self, symbol: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT timeframe
                FROM market_data
                WHERE symbol = ?
                ORDER BY timeframe
                """,
                (symbol,),
            ).fetchall()
        return [row["timeframe"] for row in rows]

    def get_latest_candle_ts(self, symbol: str, timeframe: str) -> Optional[int]:
        with self._connect() as conn:
            mapping = self._map_columns(
                conn, "market_data", MARKET_DATA_MAPPING, required=("timestamp",)
            )
            ts_col = mapping["timestamp"]
            row = conn.execute(
                f"""
                SELECT MAX({ts_col}) AS max_ts
                FROM market_data
                WHERE symbol = ? AND timeframe = ?
                """,
                (symbol, timeframe),
            ).fetchone()
        return int(row["max_ts"]) if row and row["max_ts"] is not None else None

    def get_candles(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        if limit <= 0:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        with self._connect() as conn:
            mapping = self._map_columns(
                conn,
                "market_data",
                MARKET_DATA_MAPPING,
                required=("timestamp", "open", "high", "low", "close"),
            )
            ts_col = mapping["timestamp"]
            o_col = mapping["open"]
            h_col = mapping["high"]
            l_col = mapping["low"]
            c_col = mapping["close"]
            v_col = mapping.get("volume")

            volume_expr = v_col if v_col else "NULL"

            rows = conn.execute(
                f"""
                SELECT {ts_col} AS timestamp,
                       {o_col} AS open,
                       {h_col} AS high,
                       {l_col} AS low,
                       {c_col} AS close,
                       {volume_expr} AS volume
                FROM market_data
                WHERE symbol = ? AND timeframe = ?
                ORDER BY {ts_col} DESC
                LIMIT ?
                """,
                (symbol, timeframe, limit),
            ).fetchall()

        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        if df.empty:
            return df

        df = df.iloc[::-1].reset_index(drop=True)
        df["timestamp"] = df["timestamp"].astype("int64")
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = df["volume"].fillna(0.0).astype(float)

        self._light_check(df)
        return df

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        """Alias for get_candles to satisfy backtest interface."""
        return self.get_candles(symbol, timeframe, limit=limit)

    def get_latest_funding(self, symbol: str) -> Optional[FundingSnapshot]:
        with self._connect() as conn:
            mapping = self._map_columns(
                conn,
                "funding_rates",
                FUNDING_MAPPING,
                required=("timestamp", "funding_rate"),
            )
            ts_col = mapping["timestamp"]
            rate_col = mapping["funding_rate"]
            next_col = mapping.get("next_funding_time")

            next_expr = next_col if next_col else "NULL"
            row = conn.execute(
                f"""
                SELECT {ts_col} AS timestamp,
                       {rate_col} AS funding_rate,
                       {next_expr} AS next_funding_time
                FROM funding_rates
                WHERE symbol = ?
                ORDER BY {ts_col} DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()

        if not row:
            return None
        return FundingSnapshot(
            symbol=symbol,
            timestamp=int(row["timestamp"]),
            funding_rate=float(row["funding_rate"]),
            next_funding_time=int(row["next_funding_time"])
            if row["next_funding_time"] is not None
            else None,
        )

    def get_funding_history(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        if limit <= 0:
            return pd.DataFrame(columns=["timestamp", "funding_rate", "next_funding_time"])

        with self._connect() as conn:
            mapping = self._map_columns(
                conn,
                "funding_rates",
                FUNDING_MAPPING,
                required=("timestamp", "funding_rate"),
            )
            ts_col = mapping["timestamp"]
            rate_col = mapping["funding_rate"]
            next_col = mapping.get("next_funding_time")
            next_expr = next_col if next_col else "NULL"

            rows = conn.execute(
                f"""
                SELECT {ts_col} AS timestamp,
                       {rate_col} AS funding_rate,
                       {next_expr} AS next_funding_time
                FROM funding_rates
                WHERE symbol = ?
                ORDER BY {ts_col} DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()

        df = pd.DataFrame(rows, columns=["timestamp", "funding_rate", "next_funding_time"])
        if df.empty:
            return df
        df = df.iloc[::-1].reset_index(drop=True)
        df["timestamp"] = df["timestamp"].astype("int64")
        df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce").astype(float)
        if "next_funding_time" in df.columns:
            df["next_funding_time"] = pd.to_numeric(
                df["next_funding_time"], errors="coerce"
            )
        return df

    def get_latest_prices(self, symbol: str) -> Optional[PriceSnapshot]:
        with self._connect() as conn:
            mapping = self._map_columns(
                conn, "price_snapshots", PRICE_MAPPING, required=("timestamp",)
            )
            ts_col = mapping["timestamp"]
            last_col = mapping.get("last")
            mark_col = mapping.get("mark")
            index_col = mapping.get("index")

            last_expr = last_col if last_col else "NULL"
            mark_expr = mark_col if mark_col else "NULL"
            index_expr = index_col if index_col else "NULL"

            row = conn.execute(
                f"""
                SELECT {ts_col} AS timestamp,
                       {last_expr} AS last,
                       {mark_expr} AS mark,
                       {index_expr} AS idx
                FROM price_snapshots
                WHERE symbol = ?
                ORDER BY {ts_col} DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()

        if not row:
            return None
        return PriceSnapshot(
            symbol=symbol,
            timestamp=int(row["timestamp"]),
            last=float(row["last"]) if row["last"] is not None else None,
            mark=float(row["mark"]) if row["mark"] is not None else None,
            index=float(row["idx"]) if row["idx"] is not None else None,
        )

    def get_latest_market_snapshot(
        self, symbol: str, timeframe: str, limit: int = 300
    ) -> MarketSnapshot:
        candles = self.get_candles(symbol, timeframe, limit=limit)
        funding = self.get_latest_funding(symbol)
        prices = self.get_latest_prices(symbol)
        return MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            funding=funding,
            prices=prices,
        )

    def _light_check(self, df: pd.DataFrame, sample_size: int = 50) -> None:
        if df.empty:
            return
        sample = df.tail(sample_size)
        if not sample["timestamp"].is_monotonic_increasing:
            print("[DataService] warning: timestamp not strictly increasing in sample.")
        max_oc = sample[["open", "close"]].max(axis=1)
        min_oc = sample[["open", "close"]].min(axis=1)
        bad_high = (sample["high"] < max_oc).sum()
        bad_low = (sample["low"] > min_oc).sum()
        if bad_high:
            print(f"[DataService] warning: {bad_high} rows with high < max(open, close).")
        if bad_low:
            print(f"[DataService] warning: {bad_low} rows with low > min(open, close).")
