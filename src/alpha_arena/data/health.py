"""Data health scanning and repair utilities."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from alpha_arena.db.connection import get_connection
from alpha_arena.ingest.okx import create_okx_client
from alpha_arena.utils.time import utc_now_ms, utc_now_s


TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
}


def timeframe_to_ms(timeframe: str) -> int:
    seconds = TIMEFRAME_SECONDS.get(timeframe)
    if seconds:
        return seconds * 1000
    if timeframe.endswith("m"):
        return int(timeframe[:-1]) * 60 * 1000
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60 * 60 * 1000
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 24 * 60 * 60 * 1000
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def iso_ts(ts_ms: int | None) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def default_range(days: int = 90) -> tuple[int, int]:
    end_ms = utc_now_ms()
    start_ms = end_ms - days * 24 * 60 * 60 * 1000
    return start_ms, end_ms


def _severity_from_missing(missing: int, duplicate: int) -> str:
    if missing >= 100 or duplicate >= 100:
        return "HIGH"
    if missing >= 20 or duplicate >= 20:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class CoverageRow:
    timeframe: str
    start_ts: Optional[int]
    end_ts: Optional[int]
    bars: int
    expected_bars_estimate: int
    missing_bars_estimate: int
    last_updated_at: Optional[int]


def coverage_summary(symbol: str) -> list[CoverageRow]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timeframe,
                   COUNT(*) AS cnt,
                   MIN(timestamp) AS min_ts,
                   MAX(timestamp) AS max_ts
            FROM market_data
            WHERE symbol = ?
            GROUP BY timeframe
            """,
            (symbol,),
        ).fetchall()

        results: list[CoverageRow] = []
        for row in rows:
            timeframe = row["timeframe"]
            count = int(row["cnt"]) if row["cnt"] is not None else 0
            min_ts = int(row["min_ts"]) if row["min_ts"] is not None else None
            max_ts = int(row["max_ts"]) if row["max_ts"] is not None else None
            interval = timeframe_to_ms(timeframe)
            expected = 0
            if min_ts is not None and max_ts is not None and max_ts >= min_ts:
                expected = int((max_ts - min_ts) // interval) + 1

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
            duplicate_count = (
                int(duplicates["dupes"]) if duplicates and duplicates["dupes"] else 0
            )
            unique_count = count - duplicate_count
            missing_est = max(expected - unique_count, 0)

            results.append(
                CoverageRow(
                    timeframe=timeframe,
                    start_ts=min_ts,
                    end_ts=max_ts,
                    bars=count,
                    expected_bars_estimate=expected,
                    missing_bars_estimate=missing_est,
                    last_updated_at=max_ts,
                )
            )
    return results


def _insert_integrity_event(
    conn,
    symbol: str,
    timeframe: str,
    event_type: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
    expected_bars: Optional[int],
    actual_bars: Optional[int],
    missing_bars: Optional[int],
    duplicate_bars: Optional[int],
    severity: str,
    detected_at: int,
    repair_job_id: Optional[str],
    details: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO candle_integrity_events (
            symbol,
            timeframe,
            event_type,
            start_ts,
            end_ts,
            expected_bars,
            actual_bars,
            missing_bars,
            duplicate_bars,
            severity,
            detected_at,
            repair_job_id,
            details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol,
            timeframe,
            event_type,
            start_ts,
            end_ts,
            expected_bars,
            actual_bars,
            missing_bars,
            duplicate_bars,
            severity,
            detected_at,
            repair_job_id,
            json.dumps(details, ensure_ascii=True),
        ),
    )


def scan_integrity(
    symbol: str,
    timeframes: Iterable[str],
    range_start_ts: Optional[int] = None,
    range_end_ts: Optional[int] = None,
) -> dict:
    start_ts, end_ts = (
        (range_start_ts, range_end_ts)
        if range_start_ts is not None and range_end_ts is not None
        else default_range()
    )
    detected_at = utc_now_s()
    summary = {"symbol": symbol, "detected_at": detected_at, "series": []}

    with get_connection() as conn:
        for timeframe in timeframes:
            interval = timeframe_to_ms(timeframe)
            rows = conn.execute(
                """
                SELECT timestamp
                FROM market_data
                WHERE symbol = ? AND timeframe = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
                """,
                (symbol, timeframe, start_ts, end_ts),
            ).fetchall()
            ts_values = [int(row["timestamp"]) for row in rows]
            if not ts_values:
                summary["series"].append(
                    {
                        "timeframe": timeframe,
                        "count": 0,
                        "gaps": 0,
                        "duplicates": 0,
                    }
                )
                continue

            counter = Counter(ts_values)
            duplicates = {ts: cnt for ts, cnt in counter.items() if cnt > 1}
            duplicate_bars = sum(cnt - 1 for cnt in duplicates.values())
            unique_ts = sorted(counter.keys())

            gap_events = 0
            for idx in range(1, len(unique_ts)):
                prev_ts = unique_ts[idx - 1]
                curr_ts = unique_ts[idx]
                delta = curr_ts - prev_ts
                if delta > interval:
                    missing = int(delta // interval) - 1
                    gap_events += 1
                    _insert_integrity_event(
                        conn,
                        symbol,
                        timeframe,
                        "GAP",
                        prev_ts + interval,
                        curr_ts - interval,
                        expected_bars=int(delta // interval) + 1,
                        actual_bars=2,
                        missing_bars=missing,
                        duplicate_bars=0,
                        severity=_severity_from_missing(missing, 0),
                        detected_at=detected_at,
                        repair_job_id=None,
                        details={
                            "delta_ms": delta,
                            "interval_ms": interval,
                            "start_iso": iso_ts(prev_ts + interval),
                            "end_iso": iso_ts(curr_ts - interval),
                        },
                    )

            for ts, cnt in duplicates.items():
                _insert_integrity_event(
                    conn,
                    symbol,
                    timeframe,
                    "DUPLICATE",
                    ts,
                    ts,
                    expected_bars=1,
                    actual_bars=cnt,
                    missing_bars=0,
                    duplicate_bars=cnt - 1,
                    severity=_severity_from_missing(0, cnt - 1),
                    detected_at=detected_at,
                    repair_job_id=None,
                    details={"timestamp_iso": iso_ts(ts), "duplicate_count": cnt},
                )

            summary["series"].append(
                {
                    "timeframe": timeframe,
                    "count": len(ts_values),
                    "gaps": gap_events,
                    "duplicates": len(duplicates),
                }
            )
        conn.commit()
    return summary


def _insert_ohlcv(conn, symbol: str, timeframe: str, candles: Iterable[list[float]]) -> int:
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


def _fetch_price_usdt(conn, currency: str) -> Optional[float]:
    if currency.upper() == "USDT":
        return 1.0
    symbol_variants = [
        f"{currency}/USDT:USDT",
        f"{currency}/USDT",
    ]
    for symbol in symbol_variants:
        row = conn.execute(
            """
            SELECT last_price, mark_price, index_price
            FROM price_snapshots
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()
        if row:
            for field in ("mark_price", "last_price", "index_price"):
                value = row[field]
                if value is not None:
                    return float(value)

        row = conn.execute(
            """
            SELECT close
            FROM market_data
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol, "1h"),
        ).fetchone()
        if row and row["close"] is not None:
            return float(row["close"])
    return None


def _create_repair_job(
    conn,
    symbol: str,
    timeframe: str,
    range_start_ts: int,
    range_end_ts: int,
) -> str:
    job_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO candle_repair_jobs (
            job_id,
            created_at,
            symbol,
            timeframe,
            range_start_ts,
            range_end_ts,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, utc_now_s(), symbol, timeframe, range_start_ts, range_end_ts, "RUNNING"),
    )
    conn.commit()
    return job_id


def _finish_repair_job(
    conn,
    job_id: str,
    status: str,
    repaired_bars: int,
    message: Optional[str],
    payload: Optional[dict],
) -> None:
    conn.execute(
        """
        UPDATE candle_repair_jobs
        SET status = ?, repaired_bars = ?, message = ?, raw_payload = ?
        WHERE job_id = ?
        """,
        (
            status,
            repaired_bars,
            message,
            json.dumps(payload, ensure_ascii=True) if payload else None,
            job_id,
        ),
    )
    conn.commit()


def repair_candles(
    symbol: str,
    timeframe: str,
    range_start_ts: int,
    range_end_ts: int,
    mode: str = "refetch",
) -> dict:
    interval = timeframe_to_ms(timeframe)
    with get_connection() as conn:
        job_id = _create_repair_job(conn, symbol, timeframe, range_start_ts, range_end_ts)

        repaired = 0
        try:
            if mode == "refetch":
                exchange = create_okx_client()
                exchange.load_markets()
                since = range_start_ts
                while since <= range_end_ts:
                    candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=200)
                    if not candles:
                        break
                    filtered = [c for c in candles if c[0] <= range_end_ts]
                    repaired += _insert_ohlcv(conn, symbol, timeframe, filtered)
                    last_ts = candles[-1][0]
                    if last_ts < since:
                        break
                    since = last_ts + interval
                    if len(candles) < 200 and last_ts >= range_end_ts:
                        break
                    time.sleep(exchange.rateLimit / 1000.0)
            else:
                prev_row = conn.execute(
                    """
                    SELECT close
                    FROM market_data
                    WHERE symbol = ? AND timeframe = ? AND timestamp < ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (symbol, timeframe, range_start_ts),
                ).fetchone()
                prev_close = float(prev_row["close"]) if prev_row and prev_row["close"] is not None else None
                if prev_close is None:
                    raise ValueError("Missing previous close for fill mode.")
                candles = []
                ts = range_start_ts
                while ts <= range_end_ts:
                    candles.append([ts, prev_close, prev_close, prev_close, prev_close, 0.0])
                    ts += interval
                repaired = _insert_ohlcv(conn, symbol, timeframe, candles)

            _finish_repair_job(
                conn,
                job_id,
                "DONE",
                repaired,
                None,
                {"mode": mode, "repaired_bars": repaired},
            )

            _insert_integrity_event(
                conn,
                symbol,
                timeframe,
                "REPAIR",
                range_start_ts,
                range_end_ts,
                expected_bars=int((range_end_ts - range_start_ts) // interval) + 1,
                actual_bars=repaired,
                missing_bars=0,
                duplicate_bars=0,
                severity="LOW",
                detected_at=utc_now_s(),
                repair_job_id=job_id,
                details={"mode": mode, "repaired_bars": repaired},
            )
            conn.commit()
        except Exception as exc:
            _finish_repair_job(conn, job_id, "FAILED", repaired, str(exc), None)
            _insert_integrity_event(
                conn,
                symbol,
                timeframe,
                "REPAIR",
                range_start_ts,
                range_end_ts,
                expected_bars=None,
                actual_bars=repaired,
                missing_bars=None,
                duplicate_bars=None,
                severity="HIGH",
                detected_at=utc_now_s(),
                repair_job_id=job_id,
                details={"mode": mode, "error": str(exc)},
            )
            conn.commit()
            raise

    return {"job_id": job_id, "repaired_bars": repaired, "mode": mode}
