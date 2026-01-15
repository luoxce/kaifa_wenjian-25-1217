"""Ingest OKX market data into the database."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))


import argparse

from alpha_arena.config import settings
from alpha_arena.db.migrate import migrate
from alpha_arena.ingest.okx import ingest_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OKX data ingestion")
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
        "--since-days",
        type=int,
        default=30,
        help="Backfill window in days (used only if no data exists).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Per-request OHLCV limit.",
    )
    parser.add_argument(
        "--max-bars",
        type=int,
        default=None,
        help="Optional cap on total bars per timeframe.",
    )
    return parser.parse_args()


def main() -> None:
    migrate()
    args = parse_args()
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    results = ingest_all(
        symbol=args.symbol,
        timeframes=timeframes,
        since_days=args.since_days,
        limit=args.limit,
        max_bars=args.max_bars,
    )
    for key, value in results.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
