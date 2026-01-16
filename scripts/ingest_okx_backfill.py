"""Backfill historical OHLCV regardless of existing data."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import argparse

from alpha_arena.config import settings
from alpha_arena.db.migrate import migrate
from alpha_arena.ingest.okx import (
    create_okx_client,
    ingest_funding_rate,
    ingest_price_snapshot,
    ingest_ohlcv,
)
from alpha_arena.utils.time import utc_now_ms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OKX historical backfill")
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
        default=730,
        help="Backfill window in days.",
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
    since_ms = utc_now_ms() - args.since_days * 24 * 60 * 60 * 1000

    exchange = create_okx_client()
    exchange.load_markets()

    funding = ingest_funding_rate(exchange, args.symbol)
    snapshot = ingest_price_snapshot(exchange, args.symbol)
    print(f"funding_rate: {funding}")
    print(f"price_snapshot: {snapshot}")

    for timeframe in timeframes:
        inserted = ingest_ohlcv(
            exchange,
            symbol=args.symbol,
            timeframe=timeframe,
            since_ms=since_ms,
            limit=args.limit,
            max_bars=args.max_bars,
            override_since=True,
        )
        print(f"ohlcv_{timeframe}: {inserted}")


if __name__ == "__main__":
    main()
