"""Smoke test for multi-strategy portfolio allocation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.decision import PortfolioDecisionEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test portfolio decision.")
    parser.add_argument(
        "--symbol",
        default=settings.okx_default_symbol,
        help="Symbol, e.g. BTC/USDT:USDT",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="Timeframe, e.g. 1h or 4h",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Number of candles used to compute indicators.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = PortfolioDecisionEngine()
    result = engine.decide(args.symbol, args.timeframe, limit=args.limit)
    if not result:
        print("Portfolio Decision: HOLD/REJECTED")
        return

    print("Portfolio Decision:")
    print(f"  regime: {result['regime']}")
    for item in result["allocations"]:
        print(
            f"  - {item['strategy_id']}: weight={item['weight']:.2f}, "
            f"score={item['score']:.2f}, perf={item['performance_score']:.2f}"
        )


if __name__ == "__main__":
    main()
