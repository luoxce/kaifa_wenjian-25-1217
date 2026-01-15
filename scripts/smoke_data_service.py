"""Smoke test for DataService."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import argparse
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test DataService")
    parser.add_argument(
        "--symbol",
        default=settings.okx_default_symbol,
        help="Symbol, e.g. BTC/USDT:USDT",
    )
    parser.add_argument(
        "--timeframe",
        default="15m",
        help="Timeframe, e.g. 15m",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Number of candles to load.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override database path (optional).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = DataService(db_path=args.db_path)

    candles = service.get_candles(args.symbol, args.timeframe, limit=args.limit)
    if candles.empty:
        print("candles: empty")
    else:
        min_ts = int(candles["timestamp"].min())
        max_ts = int(candles["timestamp"].max())
        last_close = float(candles["close"].iloc[-1])
        print(
            f"candles: rows={len(candles)}, min_ts={min_ts}, max_ts={max_ts}, "
            f"last_close={last_close}"
        )

    funding = service.get_latest_funding(args.symbol)
    print("funding:", asdict(funding) if funding else None)

    prices = service.get_latest_prices(args.symbol)
    print("prices:", asdict(prices) if prices else None)

    snapshot = service.get_latest_market_snapshot(
        args.symbol, args.timeframe, limit=args.limit
    )
    print(
        "snapshot:",
        {
            "symbol": snapshot.symbol,
            "timeframe": snapshot.timeframe,
            "candles_rows": len(snapshot.candles),
            "funding": asdict(snapshot.funding) if snapshot.funding else None,
            "prices": asdict(snapshot.prices) if snapshot.prices else None,
        },
    )


if __name__ == "__main__":
    main()
