"""Sync order status from exchange into the local database."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.execution.order_tracker import OrderTracker
from alpha_arena.utils.time import utc_now_ms


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh live order status.")
    parser.add_argument(
        "--order-ids",
        default="",
        help="Comma-separated client_order_id list (default: all open orders).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Sync open/closed orders and trade history from exchange.",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols for full sync (default: OKX_DEFAULT_SYMBOL).",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=0,
        help="Lookback days for full sync (0 uses exchange default).",
    )
    parser.add_argument(
        "--since-ms",
        type=int,
        default=0,
        help="Override since timestamp in ms for full sync.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Page size for exchange history fetches (default: 100).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously with sleep interval.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Loop interval seconds (default: 10).",
    )
    return parser.parse_args()


def run_once(
    tracker: OrderTracker,
    order_ids: list[str],
    *,
    full: bool,
    symbols: list[str],
    since_ms: int | None,
    limit: int,
) -> None:
    try:
        if full:
            result = tracker.sync_exchange_history(
                symbols=symbols or None,
                since_ms=since_ms,
                limit=limit,
            )
            logger.info("Full order sync completed. Result=%s", result)
        else:
            updated = tracker.sync_orders(order_ids or None, only_open=not order_ids)
            logger.info("Order sync completed. Updated=%s", updated)
    except Exception as exc:
        logger.exception("Order sync failed: %s", exc)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args()
    order_ids = [o.strip() for o in args.order_ids.split(",") if o.strip()]
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    since_ms = args.since_ms if args.since_ms > 0 else None
    if since_ms is None and args.since_days > 0:
        since_ms = utc_now_ms() - args.since_days * 24 * 60 * 60 * 1000
    tracker = OrderTracker()

    if not args.loop:
        run_once(
            tracker,
            order_ids,
            full=args.full,
            symbols=symbols,
            since_ms=since_ms,
            limit=args.limit,
        )
        return

    while True:
        run_once(
            tracker,
            order_ids,
            full=args.full,
            symbols=symbols,
            since_ms=since_ms,
            limit=args.limit,
        )
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
