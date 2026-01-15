"""Scheduled OKX ingestion with overlap to avoid gaps."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys
import time

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.ingest.okx import create_okx_client, ingest_ohlcv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scheduled OKX ingestion")
    parser.add_argument(
        "--symbol",
        default=settings.okx_default_symbol,
        help="Symbol, e.g. BTC/USDT:USDT",
    )
    parser.add_argument(
        "--timeframes",
        default=",".join(settings.okx_timeframes),
        help="Comma-separated timeframes, e.g. 15m,1h,4h,1d",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Scheduler sleep interval in seconds (default 300 = 5 min)",
    )
    parser.add_argument(
        "--overlap-bars",
        type=int,
        default=2,
        help="Overlap bars to re-fetch for dedupe safety (default 2)",
    )
    return parser.parse_args()


def timeframe_to_ms(timeframe: str) -> int:
    if timeframe.endswith("m"):
        return int(timeframe[:-1]) * 60 * 1000
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60 * 60 * 1000
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 24 * 60 * 60 * 1000
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def get_last_ts(conn, symbol: str, timeframe: str) -> int | None:
    row = conn.execute(
        """
        SELECT MAX(timestamp) AS max_ts
        FROM market_data
        WHERE symbol = ? AND timeframe = ?
        """,
        (symbol, timeframe),
    ).fetchone()
    return int(row["max_ts"]) if row and row["max_ts"] is not None else None


def run_once(symbol: str, timeframes: list[str], overlap_bars: int) -> dict[str, int]:
    exchange = create_okx_client()
    exchange.load_markets()
    results: dict[str, int] = {}
    with get_connection() as conn:
        for timeframe in timeframes:
            last_ts = get_last_ts(conn, symbol, timeframe)
            interval_ms = timeframe_to_ms(timeframe)
            if last_ts is None:
                since_ms = None
            else:
                since_ms = max(last_ts - overlap_bars * interval_ms, 0)
            inserted = ingest_ohlcv(
                exchange,
                symbol=symbol,
                timeframe=timeframe,
                since_ms=since_ms,
                limit=200,
                max_bars=None,
                override_since=True,
            )
            results[timeframe] = inserted
            time.sleep(exchange.rateLimit / 1000.0)
    return results


def main() -> None:
    args = parse_args()
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    print(
        f"Scheduler started: symbol={args.symbol}, timeframes={timeframes}, "
        f"interval={args.interval_seconds}s, overlap_bars={args.overlap_bars}"
    )
    while True:
        try:
            results = run_once(args.symbol, timeframes, args.overlap_bars)
            for tf, count in results.items():
                print(f"{tf}: {count} rows")
        except Exception as exc:  # pragma: no cover
            print(f"[scheduler] error: {exc}")
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
