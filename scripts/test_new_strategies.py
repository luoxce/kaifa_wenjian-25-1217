"""Basic functional test for implemented strategies."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys
from typing import List, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.data import DataService
from alpha_arena.strategies import StrategyLibrary
from alpha_arena.strategies.signals import SignalType, StrategySignal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy functional test")
    parser.add_argument(
        "--symbol",
        required=True,
        help="Symbol, e.g. BTC/USDT:USDT",
    )
    parser.add_argument(
        "--timeframe",
        required=True,
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
        help="Comma-separated strategy keys; empty uses all implemented strategies.",
    )
    return parser.parse_args()


def _signal_type_ok(signal_type: object) -> bool:
    if isinstance(signal_type, SignalType):
        return True
    if isinstance(signal_type, str):
        return signal_type in SignalType._value2member_map_
    return False


def _validate_signal(
    signal: StrategySignal, strategy_key: str, symbol: str, timeframe: str
) -> List[str]:
    errors: List[str] = []
    if not isinstance(signal, StrategySignal):
        return ["signal is not StrategySignal"]

    if signal.strategy != strategy_key:
        errors.append(f"strategy mismatch: {signal.strategy}")
    if signal.symbol != symbol:
        errors.append(f"symbol mismatch: {signal.symbol}")
    if signal.timeframe != timeframe:
        errors.append(f"timeframe mismatch: {signal.timeframe}")
    if not _signal_type_ok(signal.signal_type):
        errors.append(f"invalid signal_type: {signal.signal_type}")
    if not isinstance(signal.timestamp, int):
        errors.append("timestamp is not int")
    if not isinstance(signal.price, (int, float)):
        errors.append("price is not numeric")
    if not isinstance(signal.confidence, (int, float)):
        errors.append("confidence is not numeric")
    elif not (0.0 <= float(signal.confidence) <= 1.0):
        errors.append(f"confidence out of range: {signal.confidence}")
    if not isinstance(signal.reasoning, str) or not signal.reasoning.strip():
        errors.append("reasoning missing")
    return errors


def _data_check(df) -> Tuple[str, List[str]]:
    if df is None:
        return "FAIL", ["data frame is None"]
    if df.empty:
        return "WARN", ["no candles returned"]
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = [col for col in required if col not in df.columns]
    if missing:
        return "FAIL", [f"missing columns: {', '.join(missing)}"]
    return "PASS", []


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
        specs = [spec for spec in library.list_all() if spec.implemented]

    if not specs:
        print("No strategies to run.")
        return

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for spec in specs:
        if not spec.implemented or not spec.factory:
            print(f"[skip] not implemented: {spec.key}")
            continue

        status = {"instantiate": "PASS", "data": "PASS", "signal": "PASS", "format": "PASS"}
        details: List[str] = []

        try:
            strategy = spec.factory(args.symbol, args.timeframe, data_service, None)
            strategy.data_limit = args.limit
        except Exception as exc:
            status["instantiate"] = "FAIL"
            details.append(f"instantiate error: {exc}")
            _print_result(spec.key, status, details)
            totals["FAIL"] += 1
            continue

        try:
            candles = strategy.get_candles()
            data_status, data_details = _data_check(candles)
            status["data"] = data_status
            details.extend(data_details)
        except Exception as exc:
            status["data"] = "FAIL"
            details.append(f"data error: {exc}")
            candles = None

        try:
            signal = strategy.generate_signal()
        except Exception as exc:
            status["signal"] = "FAIL"
            details.append(f"signal error: {exc}")
            _print_result(spec.key, status, details)
            totals["FAIL"] += 1
            continue

        format_errors = _validate_signal(signal, spec.key, args.symbol, args.timeframe)
        if format_errors:
            status["format"] = "FAIL"
            details.extend(format_errors)
        else:
            details.append(f"signal={asdict(signal)}")

        _print_result(spec.key, status, details)
        worst = _worst_status(status.values())
        totals[worst] += 1

    print("Summary:")
    print(f"  PASS={totals['PASS']} WARN={totals['WARN']} FAIL={totals['FAIL']}")


def _worst_status(values) -> str:
    if "FAIL" in values:
        return "FAIL"
    if "WARN" in values:
        return "WARN"
    return "PASS"


def _print_result(key: str, status: dict, details: List[str]) -> None:
    status_line = (
        f"{key}: instantiate={status['instantiate']} "
        f"data={status['data']} "
        f"signal={status['signal']} "
        f"format={status['format']}"
    )
    print(status_line)
    for item in details:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
