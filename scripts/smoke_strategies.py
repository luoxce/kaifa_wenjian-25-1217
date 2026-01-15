"""Smoke test for strategy signals via StrategyLibrary."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.strategies import StrategyLibrary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy smoke test")
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
        default=300,
        help="Number of candles to load for each strategy.",
    )
    parser.add_argument(
        "--strategies",
        default="",
        help="Comma-separated strategy keys; empty uses enabled strategies.",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled strategies (implemented ones only).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_service = DataService()
    library = StrategyLibrary(data_service)

    if args.strategies.strip():
        keys = [k.strip() for k in args.strategies.split(",") if k.strip()]
        specs = []
        for key in keys:
            spec = library.get(key)
            if spec:
                specs.append(spec)
            else:
                print(f"[skip] unknown strategy: {key}")
    else:
        specs = library.list_enabled()
        if args.include_disabled:
            specs = [spec for spec in library.list_all() if spec.implemented]

    if not specs:
        print("No strategies to run.")
        return

    for spec in specs:
        if not spec.implemented or not spec.factory:
            print(f"[skip] not implemented: {spec.key}")
            continue
        try:
            strategy = spec.factory(args.symbol, args.timeframe, data_service, None)
            strategy.data_limit = args.limit
            signal = strategy.generate_signal()
            payload = asdict(signal)
            print(f"{spec.key}: {payload}")
        except Exception as exc:
            print(f"[error] {spec.key}: {exc}")


if __name__ == "__main__":
    main()
