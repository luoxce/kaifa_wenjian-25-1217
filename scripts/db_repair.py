"""Repair missing OHLCV gaps by backfilling from OKX."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
import time
from typing import Iterable

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.ingest.okx import create_okx_client
from alpha_arena.utils.time import utc_now_s


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair OHLCV gaps")
    parser.add_argument("--symbol", required=True, help="Symbol, e.g. BTC/USDT:USDT")
    parser.add_argument("--timeframe", required=True, help="Timeframe, e.g. 15m")
    parser.add_argument(
        "--gap",
        action="append",
        help="Gap as start_ts,end_ts (UTC ms). Can be repeated.",
    )
    parser.add_argument(
        "--gaps-file",
        help="Path to db_stats JSON report or a list of gaps.",
    )
    parser.add_argument(
        "--max-gaps",
        type=int,
        default=None,
        help="Limit gaps processed in auto mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Per-request OHLCV limit.",
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


def parse_gap_value(value: str) -> tuple[int, int]:
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"Invalid gap: {value}. Expected start_ts,end_ts")
    return int(parts[0]), int(parts[1])


def load_gaps_from_file(path: Path, symbol: str, timeframe: str) -> list[tuple[int, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "market_data" in data:
        series_list = data.get("market_data", {}).get("series", [])
        for series in series_list:
            if series.get("symbol") == symbol and series.get("timeframe") == timeframe:
                gaps = []
                for gap in series.get("gap_list", []):
                    gaps.append((int(gap["start_ts"]), int(gap["end_ts"])))
                return gaps
        return []
    if isinstance(data, list):
        gaps = []
        for item in data:
            if isinstance(item, list) and len(item) == 2:
                gaps.append((int(item[0]), int(item[1])))
            elif isinstance(item, dict) and "start_ts" in item and "end_ts" in item:
                gaps.append((int(item["start_ts"]), int(item["end_ts"])))
        return gaps
    raise ValueError("Unsupported gaps file format.")


def find_gaps(conn, symbol: str, timeframe: str, max_gaps: int | None) -> list[tuple[int, int]]:
    interval_ms = timeframe_to_ms(timeframe)
    rows = conn.execute(
        """
        SELECT timestamp
        FROM market_data
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp
        """,
        (symbol, timeframe),
    ).fetchall()
    if not rows:
        return []
    ts_values = sorted({int(row["timestamp"]) for row in rows})
    gaps: list[tuple[int, int]] = []
    for idx in range(1, len(ts_values)):
        prev_ts = ts_values[idx - 1]
        curr_ts = ts_values[idx]
        delta = curr_ts - prev_ts
        if delta > interval_ms:
            gaps.append((prev_ts + interval_ms, curr_ts - interval_ms))
            if max_gaps and len(gaps) >= max_gaps:
                break
    return gaps


def insert_ohlcv(conn, symbol: str, timeframe: str, candles: Iterable[list[float]]) -> int:
    rows = [
        (symbol, timeframe, c[0], c[1], c[2], c[3], c[4], c[5]) for c in candles
    ]
    if not rows:
        return 0
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


def start_run(conn, symbol: str, timeframe: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO ingestion_runs (source, symbol, timeframe, data_type, started_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("okx", symbol, timeframe, "ohlcv_repair", utc_now_s(), "running"),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn, run_id: int, status: str, rows_inserted: int, error: str | None) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs
        SET ended_at = ?, status = ?, rows_inserted = ?, error = ?
        WHERE id = ?
        """,
        (utc_now_s(), status, rows_inserted, error, run_id),
    )
    conn.commit()


def backfill_gap(
    exchange,
    conn,
    symbol: str,
    timeframe: str,
    start_ts: int,
    end_ts: int,
    limit: int,
) -> int:
    interval_ms = timeframe_to_ms(timeframe)
    since = start_ts
    inserted_total = 0
    while since <= end_ts:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not candles:
            break
        filtered = [c for c in candles if c[0] <= end_ts]
        inserted_total += insert_ohlcv(conn, symbol, timeframe, filtered)
        last_ts = candles[-1][0]
        if last_ts < since:
            break
        since = last_ts + interval_ms
        if len(candles) < limit and last_ts >= end_ts:
            break
        time.sleep(exchange.rateLimit / 1000.0)
    return inserted_total


def main() -> None:
    args = parse_args()
    gaps: list[tuple[int, int]] = []

    if args.gap:
        for value in args.gap:
            gaps.append(parse_gap_value(value))
    if args.gaps_file:
        gaps.extend(load_gaps_from_file(Path(args.gaps_file), args.symbol, args.timeframe))

    with get_connection() as conn:
        if not gaps:
            gaps = find_gaps(conn, args.symbol, args.timeframe, args.max_gaps)

        if not gaps:
            print("No gaps found.")
            return

        exchange = create_okx_client()
        exchange.load_markets()

        run_id = start_run(conn, args.symbol, args.timeframe)
        inserted = 0
        try:
            for start_ts, end_ts in gaps:
                inserted += backfill_gap(
                    exchange,
                    conn,
                    args.symbol,
                    args.timeframe,
                    start_ts,
                    end_ts,
                    args.limit,
                )
            finish_run(conn, run_id, "success", inserted, None)
        except Exception as exc:  # pragma: no cover
            finish_run(conn, run_id, "failed", inserted, str(exc))
            raise

    print(f"Inserted rows (attempted): {inserted}")


if __name__ == "__main__":
    main()
