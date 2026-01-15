"""Sync order status from exchange into the local database."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.execution.order_tracker import OrderTracker


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh live order status.")
    parser.add_argument(
        "--order-ids",
        default="",
        help="Comma-separated client_order_id list (default: all open orders).",
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


def run_once(tracker: OrderTracker, order_ids: list[str]) -> None:
    try:
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
    tracker = OrderTracker()

    if not args.loop:
        run_once(tracker, order_ids)
        return

    while True:
        run_once(tracker, order_ids)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
