"""Database stats and data quality checks."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
from datetime import datetime, timezone

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection


TABLE_TIME_COLUMN_CANDIDATES = (
    "timestamp",
    "created_at",
    "updated_at",
    "started_at",
    "ended_at",
    "start_time",
    "end_time",
    "applied_at",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Database stats and quality checks")
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for JSON report output",
    )
    parser.add_argument(
        "--max-gaps",
        type=int,
        default=None,
        help="Limit gap_list entries per symbol/timeframe",
    )
    return parser.parse_args()


def utc_iso(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def timeframe_to_ms(timeframe: str) -> int:
    if timeframe.endswith("m"):
        return int(timeframe[:-1]) * 60 * 1000
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60 * 60 * 1000
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 24 * 60 * 60 * 1000
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def get_existing_tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def get_table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def pick_time_column(columns: set[str]) -> str | None:
    for candidate in TABLE_TIME_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate
    return None


def table_stats(conn, table: str) -> dict:
    columns = get_table_columns(conn, table)
    time_col = pick_time_column(columns)
    result = {"rows": 0, "time_column": time_col}

    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
    result["rows"] = int(row["cnt"]) if row else 0

    if time_col:
        row = conn.execute(
            f"SELECT MIN({time_col}) AS min_ts, MAX({time_col}) AS max_ts FROM {table}"
        ).fetchone()
        min_ts = int(row["min_ts"]) if row and row["min_ts"] is not None else None
        max_ts = int(row["max_ts"]) if row and row["max_ts"] is not None else None
        result.update(
            {
                "min_ts": min_ts,
                "max_ts": max_ts,
                "last_ts": max_ts,
                "min_iso": utc_iso(min_ts),
                "max_iso": utc_iso(max_ts),
                "last_iso": utc_iso(max_ts),
            }
        )
    return result


def market_data_quality(conn, max_gaps: int | None) -> dict:
    report = {"series": [], "sanity_totals": {}}

    sanity_volume = conn.execute(
        "SELECT COUNT(*) AS cnt FROM market_data WHERE volume < 0"
    ).fetchone()
    sanity_high_low = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM market_data
        WHERE high < open
           OR high < close
           OR low > open
           OR low > close
        """
    ).fetchone()
    report["sanity_totals"] = {
        "invalid_volume": int(sanity_volume["cnt"]) if sanity_volume else 0,
        "invalid_high_low": int(sanity_high_low["cnt"]) if sanity_high_low else 0,
    }

    pairs = conn.execute(
        "SELECT symbol, timeframe, COUNT(*) AS cnt FROM market_data GROUP BY symbol, timeframe"
    ).fetchall()

    for pair in pairs:
        symbol = pair["symbol"]
        timeframe = pair["timeframe"]
        interval_ms = timeframe_to_ms(timeframe)

        counts = conn.execute(
            """
            SELECT COUNT(*) AS cnt, MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts
            FROM market_data
            WHERE symbol = ? AND timeframe = ?
            """,
            (symbol, timeframe),
        ).fetchone()

        total_count = int(counts["cnt"]) if counts else 0
        min_ts = int(counts["min_ts"]) if counts and counts["min_ts"] is not None else None
        max_ts = int(counts["max_ts"]) if counts and counts["max_ts"] is not None else None

        duplicates = conn.execute(
            """
            SELECT SUM(cnt - 1) AS dupes
            FROM (
                SELECT COUNT(*) AS cnt
                FROM market_data
                WHERE symbol = ? AND timeframe = ?
                GROUP BY timestamp
                HAVING cnt > 1
            )
            """,
            (symbol, timeframe),
        ).fetchone()
        duplicate_count = int(duplicates["dupes"]) if duplicates and duplicates["dupes"] else 0

        unique_count = total_count - duplicate_count

        if min_ts is None or max_ts is None:
            expected_bars = 0
        else:
            expected_bars = int((max_ts - min_ts) // interval_ms) + 1

        missing = max(expected_bars - unique_count, 0)

        timestamps = conn.execute(
            """
            SELECT timestamp
            FROM market_data
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp
            """,
            (symbol, timeframe),
        ).fetchall()
        ts_values = [int(row["timestamp"]) for row in timestamps]
        unique_ts = sorted(set(ts_values))

        non_monotonic = 0
        gap_list = []
        for idx in range(1, len(unique_ts)):
            prev_ts = unique_ts[idx - 1]
            curr_ts = unique_ts[idx]
            if curr_ts <= prev_ts:
                non_monotonic += 1
            delta = curr_ts - prev_ts
            if delta > interval_ms:
                missing_bars = int(delta // interval_ms) - 1
                gap = {
                    "start_ts": prev_ts + interval_ms,
                    "end_ts": curr_ts - interval_ms,
                    "start_iso": utc_iso(prev_ts + interval_ms),
                    "end_iso": utc_iso(curr_ts - interval_ms),
                    "missing_bars": missing_bars,
                    "delta_ms": delta,
                }
                gap_list.append(gap)
                if max_gaps and len(gap_list) >= max_gaps:
                    break

        report["series"].append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "interval_ms": interval_ms,
                "count": total_count,
                "unique_count": unique_count,
                "min_ts": min_ts,
                "max_ts": max_ts,
                "last_ts": max_ts,
                "min_iso": utc_iso(min_ts),
                "max_iso": utc_iso(max_ts),
                "last_iso": utc_iso(max_ts),
                "expected_bars": expected_bars,
                "missing": missing,
                "duplicate_count": duplicate_count,
                "non_monotonic": non_monotonic,
                "gap_list": gap_list,
            }
        )

    return report


def print_summary(report: dict) -> None:
    print("Database:", report["database_url"])
    print("Generated:", report["generated_at"])
    print("")
    print("Table summary:")
    for table, stats in report["tables"].items():
        rows = stats.get("rows")
        min_iso = stats.get("min_iso")
        max_iso = stats.get("max_iso")
        print(f"- {table}: rows={rows}, min={min_iso}, max={max_iso}")

    print("")
    print("Market data summary:")
    for series in report["market_data"]["series"]:
        print(
            f"- {series['symbol']} {series['timeframe']}: "
            f"count={series['count']}, expected={series['expected_bars']}, "
            f"missing={series['missing']}, duplicates={series['duplicate_count']}, "
            f"last={series['last_iso']}"
        )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"db_stats_{datetime.now().strftime('%Y%m%d')}.json"

    with get_connection() as conn:
        existing_tables = get_existing_tables(conn)

        tables = {}
        for table in sorted(existing_tables):
            tables[table] = table_stats(conn, table)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_url": settings.database_url,
            "tables": tables,
            "market_data": market_data_quality(conn, args.max_gaps),
        }

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(report)
    print("")
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
