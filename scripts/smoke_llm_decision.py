"""Smoke test for LLM decision flow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.decision import DecisionEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test LLM decision flow.")
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
        default=100,
        help="Number of candles used to compute indicators.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = DecisionEngine()
    decision = engine.decide(args.symbol, args.timeframe, limit=args.limit)

    if decision is None:
        print("Decision: HOLD/REJECTED")
        if engine.selector.last_result:
            print("Reason:", engine.selector.last_result.reasoning)
            if engine.selector.last_result.raw_response:
                print("LLM Error:", engine.selector.last_result.raw_response)
        return

    print("Decision:")
    print(f"  strategy: {decision.selected_strategy_id}")
    print(f"  regime: {decision.market_regime}")
    print(f"  confidence: {decision.confidence}")
    print(f"  reasoning: {decision.reasoning}")

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, symbol, timeframe, action, confidence, reasoning, timestamp
            FROM decisions
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    if row:
        print("Last decisions row:")
        print(
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "action": row["action"],
                "confidence": row["confidence"],
                "reasoning": row["reasoning"],
                "timestamp": row["timestamp"],
            }
        )


if __name__ == "__main__":
    main()
