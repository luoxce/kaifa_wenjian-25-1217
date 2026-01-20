"""Run continuous trading cycles on a fixed interval."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys
from typing import List

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.decision import DecisionEngine, PortfolioDecisionEngine
from alpha_arena.execution import PortfolioAllocator
from alpha_arena.execution.okx_executor import OKXOrderExecutor
from alpha_arena.execution.order_tracker import OrderTracker
from alpha_arena.execution.simulated_executor import SimulatedOrderExecutor
from alpha_arena.models.order import Order
from alpha_arena.risk import RiskManager


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trading loop on schedule.")
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
        "--interval",
        type=int,
        default=900,
        help="Loop interval seconds (default: 900 = 15min).",
    )
    parser.add_argument(
        "--decision-mode",
        choices=("portfolio", "llm"),
        default="portfolio",
        help="Decision source (portfolio or llm).",
    )
    parser.add_argument(
        "--trade",
        action="store_true",
        help="Actually send orders (requires TRADING_ENABLED=true).",
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


def _decisions_from_llm(result) -> dict:
    allocations = result.strategy_allocations or []
    if not allocations:
        return {}
    total_position = result.total_position
    scale = 1.0
    sign = 1.0
    if total_position is not None:
        try:
            total_val = float(total_position)
        except (TypeError, ValueError):
            total_val = 1.0
        scale = abs(total_val)
        sign = -1.0 if total_val < 0 else 1.0
    decisions = {}
    for alloc in allocations:
        try:
            weight = float(alloc.weight) * scale * sign
        except (TypeError, ValueError):
            continue
        if weight == 0:
            continue
        decisions[alloc.strategy_id] = weight
    return decisions


def run_cycle(args: argparse.Namespace, decision_engine) -> None:
    if args.decision_mode == "llm":
        result = decision_engine.decide(args.symbol, args.timeframe, limit=args.limit)
        if not result:
            logger.info("Decision: HOLD (llm rejected or empty)")
            return
        decisions = _decisions_from_llm(result)
        if not decisions:
            logger.info("Decision: HOLD (llm allocations empty)")
            return
    else:
        decision = decision_engine.decide(args.symbol, args.timeframe, limit=args.limit)
        if not decision:
            logger.info("Decision: HOLD (no allocation)")
            return
        decisions = {item["strategy_id"]: item["weight"] for item in decision["allocations"]}

    total_equity = load_total_equity(args.equity)
    if total_equity <= 0:
        logger.warning("Total equity not available; set --equity or record balances.")
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
        logger.info("Allocation plan empty.")
        return

    for item in plan:
        logger.info(
            "Allocation plan: %s weight=%.2f target_notional=%.2f",
            item.strategy_id,
            item.weight,
            item.target_notional,
        )

    if not orders:
        logger.info("No orders generated (diff below threshold).")
        return

    if not args.trade or not settings.trading_enabled:
        logger.info("Trade disabled; skipping order execution.")
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
            logger.warning("Order blocked by risk: %s", reason)
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
        logger.info("Order executed: %s -> %s", executed.order_id, executed.status.value)
        if isinstance(executor, OKXOrderExecutor) and settings.okx_wait_fill:
            executed = executor.wait_for_fill(
                executed.order_id,
                timeout_s=settings.okx_fill_timeout_s,
                poll_interval_s=settings.okx_fill_interval_s,
            )
            logger.info("Order status: %s -> %s", executed.order_id, executed.status.value)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args()
    decision_engine = (
        DecisionEngine() if args.decision_mode == "llm" else PortfolioDecisionEngine()
    )
    tracker = OrderTracker() if args.executor == "okx" else None
    executor = OKXOrderExecutor() if args.executor == "okx" else None

    while True:
        try:
            if executor and settings.okx_sync_account:
                executor.sync_account_state([args.symbol])
            if tracker:
                tracker.sync_orders(only_open=True)
            run_cycle(args, decision_engine)
        except Exception as exc:
            logger.exception("Trading cycle error: %s", exc)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
