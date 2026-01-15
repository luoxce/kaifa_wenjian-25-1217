"""OKX data ingestion."""

from __future__ import annotations

import os
import time
from typing import Iterable, Optional

import ccxt

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.utils.time import utc_now_ms, utc_now_s


def _load_proxies() -> dict[str, str] | None:
    http_proxy = (
        os.getenv("OKX_HTTP_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )
    https_proxy = (
        os.getenv("OKX_HTTPS_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
    )
    all_proxy = (
        os.getenv("OKX_ALL_PROXY")
        or os.getenv("ALL_PROXY")
        or os.getenv("all_proxy")
    )

    proxies: dict[str, str] = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    if not proxies and all_proxy:
        proxies["http"] = all_proxy
        proxies["https"] = all_proxy
    return proxies or None


def create_okx_client() -> ccxt.okx:
    exchange = ccxt.okx(
        {
            "apiKey": settings.okx_api_key,
            "secret": settings.okx_api_secret,
            "password": settings.okx_password,
            "enableRateLimit": True,
            "timeout": 30000,
            "options": {"defaultType": settings.okx_default_market},
        }
    )
    proxies = _load_proxies()
    if proxies:
        exchange.proxies = proxies
    try:
        exchange.set_sandbox_mode(settings.okx_is_demo)
    except AttributeError:
        exchange.options["sandboxMode"] = settings.okx_is_demo
    if settings.okx_default_market:
        exchange.options["fetchMarkets"] = {"types": [settings.okx_default_market]}
    return exchange


def _start_ingestion_run(conn, symbol: str, timeframe: Optional[str], data_type: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO ingestion_runs (source, symbol, timeframe, data_type, started_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("okx", symbol, timeframe, data_type, utc_now_s(), "running"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _finish_ingestion_run(
    conn, run_id: int, status: str, rows_inserted: int, error: str | None = None
) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET ended_at = ?, status = ?, rows_inserted = ?, error = ?
        WHERE id = ?
        """,
        (utc_now_s(), status, rows_inserted, error, run_id),
    )
    conn.commit()


def _get_latest_ohlcv_timestamp(conn, symbol: str, timeframe: str) -> Optional[int]:
    row = conn.execute(
        """
        SELECT MAX(timestamp) AS max_ts
        FROM market_data
        WHERE symbol = ? AND timeframe = ?
        """,
        (symbol, timeframe),
    ).fetchone()
    return int(row["max_ts"]) if row and row["max_ts"] is not None else None


def _insert_ohlcv(conn, symbol: str, timeframe: str, candles: list[list[float]]) -> int:
    if not candles:
        return 0
    rows = [
        (symbol, timeframe, c[0], c[1], c[2], c[3], c[4], c[5]) for c in candles
    ]
    conn.executemany(
        """
        INSERT INTO market_data
        (symbol, timeframe, timestamp, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, timestamp) DO NOTHING
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def ingest_ohlcv(
    exchange: ccxt.okx,
    symbol: str,
    timeframe: str,
    since_ms: Optional[int] = None,
    limit: int = 200,
    max_bars: Optional[int] = None,
    override_since: bool = False,
) -> int:
    timeframe_ms = int(exchange.parse_timeframe(timeframe) * 1000)
    total = 0
    with get_connection() as conn:
        last_ts = _get_latest_ohlcv_timestamp(conn, symbol, timeframe)
        if override_since and since_ms is not None:
            since = max(int(since_ms), 0)
        elif last_ts is not None:
            since = last_ts + timeframe_ms
        else:
            since = since_ms or (utc_now_ms() - 30 * 24 * 60 * 60 * 1000)

        run_id = _start_ingestion_run(conn, symbol, timeframe, "ohlcv")
        try:
            while True:
                candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
                if not candles:
                    break
                inserted = _insert_ohlcv(conn, symbol, timeframe, candles)
                total += inserted
                since = candles[-1][0] + timeframe_ms
                if max_bars and total >= max_bars:
                    break
                if len(candles) < limit:
                    break
            _finish_ingestion_run(conn, run_id, "success", total)
        except Exception as exc:  # pragma: no cover - runtime ingestion guard
            _finish_ingestion_run(conn, run_id, "failed", total, str(exc))
            raise
    return total


def ingest_funding_rate(exchange: ccxt.okx, symbol: str) -> int:
    with get_connection() as conn:
        run_id = _start_ingestion_run(conn, symbol, None, "funding_rate")
        try:
            funding = exchange.fetch_funding_rate(symbol)
            timestamp = funding.get("timestamp") or utc_now_ms()
            rate = funding.get("fundingRate")
            next_time = funding.get("nextFundingTimestamp")
            if rate is None:
                _finish_ingestion_run(conn, run_id, "skipped", 0, "missing fundingRate")
                return 0
            conn.execute(
                """
                INSERT INTO funding_rates (symbol, timestamp, funding_rate, next_funding_time)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO NOTHING
                """,
                (symbol, timestamp, rate, next_time),
            )
            conn.commit()
            _finish_ingestion_run(conn, run_id, "success", 1)
            return 1
        except Exception as exc:  # pragma: no cover
            _finish_ingestion_run(conn, run_id, "failed", 0, str(exc))
            raise


def ingest_price_snapshot(exchange: ccxt.okx, symbol: str) -> int:
    with get_connection() as conn:
        run_id = _start_ingestion_run(conn, symbol, None, "price_snapshot")
        try:
            ticker = exchange.fetch_ticker(symbol)
            timestamp = ticker.get("timestamp") or utc_now_ms()
            last_price = ticker.get("last")
            mark_price = ticker.get("mark")
            index_price = ticker.get("index")
            conn.execute(
                """
                INSERT INTO price_snapshots (symbol, timestamp, last_price, mark_price, index_price)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO NOTHING
                """,
                (symbol, timestamp, last_price, mark_price, index_price),
            )
            conn.commit()
            _finish_ingestion_run(conn, run_id, "success", 1)
            return 1
        except Exception as exc:  # pragma: no cover
            _finish_ingestion_run(conn, run_id, "failed", 0, str(exc))
            raise


def ingest_open_interest(exchange: ccxt.okx, symbol: str) -> int:
    with get_connection() as conn:
        run_id = _start_ingestion_run(conn, symbol, None, "open_interest")
        try:
            data = exchange.fetch_open_interest(symbol)
            timestamp = data.get("timestamp") or utc_now_ms()
            oi = data.get("openInterest")
            oi_value = data.get("openInterestValue")
            if oi is None:
                _finish_ingestion_run(conn, run_id, "skipped", 0, "missing openInterest")
                return 0
            conn.execute(
                """
                INSERT INTO open_interest (symbol, timestamp, open_interest, open_interest_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO NOTHING
                """,
                (symbol, timestamp, oi, oi_value),
            )
            conn.commit()
            _finish_ingestion_run(conn, run_id, "success", 1)
            return 1
        except Exception as exc:  # pragma: no cover
            _finish_ingestion_run(conn, run_id, "failed", 0, str(exc))
            raise


def ingest_all(
    symbol: str,
    timeframes: Iterable[str],
    since_days: int = 30,
    limit: int = 200,
    max_bars: Optional[int] = None,
) -> dict[str, int]:
    exchange = create_okx_client()
    exchange.load_markets()
    since_ms = utc_now_ms() - since_days * 24 * 60 * 60 * 1000

    results = {"funding_rate": 0, "price_snapshot": 0, "open_interest": 0}
    results["funding_rate"] = ingest_funding_rate(exchange, symbol)
    results["price_snapshot"] = ingest_price_snapshot(exchange, symbol)

    try:
        results["open_interest"] = ingest_open_interest(exchange, symbol)
    except Exception:
        results["open_interest"] = 0

    for timeframe in timeframes:
        inserted = ingest_ohlcv(
            exchange,
            symbol=symbol,
            timeframe=timeframe,
            since_ms=since_ms,
            limit=limit,
            max_bars=max_bars,
        )
        results[f"ohlcv_{timeframe}"] = inserted
        time.sleep(exchange.rateLimit / 1000.0)

    return results
