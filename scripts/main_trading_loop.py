"""Single-pass trading loop: decision -> allocation -> risk -> execution."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.decision import PortfolioDecisionEngine
from alpha_arena.execution import PortfolioAllocator
from alpha_arena.execution.okx_executor import OKXOrderExecutor
from alpha_arena.execution.simulated_executor import SimulatedOrderExecutor
from alpha_arena.models.order import Order
from alpha_arena.risk import RiskManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one trading cycle.")
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
        help="Candles used for decision.",
    )
    parser.add_argument(
        "--executor",
        choices=("simulated", "okx"),
        default="simulated",
        help="Execution backend.",
    )
    parser.add_argument(
        "--equity",
        type=float,
        default=0.0,
        help="Override total equity (USDT).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute orders but do not send to executor.",
    )
    return parser.parse_args()


def load_total_equity(default_equity: float) -> float:
    if default_equity > 0:
        return default_equity
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT total
            FROM balances
            WHERE currency = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            ("USDT",),
        ).fetchone()
    if row and row["total"] is not None:
        return float(row["total"])
    return 0.0


def load_positions(symbol: str) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT symbol, side, size, entry_price
            FROM positions
            WHERE symbol = ?
            ORDER BY updated_at DESC
            """,
            (symbol,),
        ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    args = parse_args()
    decision_engine = PortfolioDecisionEngine()
    decision = decision_engine.decide(args.symbol, args.timeframe, limit=args.limit)
    if not decision:
        print("Decision: HOLD (no allocation)")
        return

    decisions = {item["strategy_id"]: item["weight"] for item in decision["allocations"]}
    total_equity = load_total_equity(args.equity)
    if total_equity <= 0:
        print("Total equity not available; set --equity or record balances.")
        return

    allocator = PortfolioAllocator()
    positions = load_positions(args.symbol)
    orders, plan = allocator.build_orders(
        symbol=args.symbol,
        decisions=decisions,
        total_equity=total_equity,
        current_positions=positions,
    )

    if not plan:
        print("Allocation plan empty.")
        return
    print("Allocation plan:")
    for item in plan:
        print(
            f"  {item.strategy_id}: weight={item.weight:.2f}, "
            f"target_notional={item.target_notional:.2f}"
        )

    if not orders:
        print("No orders generated (diff below threshold).")
        return

    if args.dry_run:
        print("Dry run orders:", [o.order_id for o in orders])
        return

    executor = (
        SimulatedOrderExecutor()
        if args.executor == "simulated"
        else OKXOrderExecutor()
    )
    risk_manager = RiskManager()

    for order in orders:
        passed, reason, _rule = risk_manager.check(order)
        if not passed:
            print(f"Order blocked by risk: {reason}")
            continue
        executed = executor.create_order(
            symbol=order.symbol,
            side=order.side,
            type=order.type,
            quantity=order.quantity,
            price=order.price,
            leverage=order.leverage,
            confidence=order.confidence,
            signal_ok=order.signal_ok,
        )
        print(f"Order executed: {executed.order_id} -> {executed.status.value}")
        if isinstance(executor, OKXOrderExecutor):
            if settings.okx_wait_fill:
                executed = executor.wait_for_fill(
                    executed.order_id,
                    timeout_s=settings.okx_fill_timeout_s,
                    poll_interval_s=settings.okx_fill_interval_s,
                )
                print(f"Order status: {executed.order_id} -> {executed.status.value}")
            if settings.okx_sync_account:
                executor.sync_account_state([args.symbol])


if __name__ == "__main__":
    main()
