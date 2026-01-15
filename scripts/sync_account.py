"""Sync balances and positions from exchange into the local database."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.execution.okx_executor import OKXOrderExecutor


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync account state from exchange.")
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols to sync (default: all).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously with sleep interval.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Loop interval seconds (default: 60).",
    )
    return parser.parse_args()


def run_once(executor: OKXOrderExecutor, symbols: list[str]) -> None:
    try:
        executor.sync_account_state(symbols or None)
        logger.info("Account sync completed.")
    except Exception as exc:
        logger.exception("Account sync failed: %s", exc)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    executor = OKXOrderExecutor()

    if not args.loop:
        run_once(executor, symbols)
        return

    while True:
        run_once(executor, symbols)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
