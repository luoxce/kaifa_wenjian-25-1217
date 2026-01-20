"""Print OKX account snapshot (balances and positions)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Iterable, List, Optional

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.ingest.okx import create_okx_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print OKX account snapshot")
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbols for positions (default: all).",
    )
    parser.add_argument(
        "--min-balance",
        type=float,
        default=1e-8,
        help="Minimum total balance to display (default: 1e-8).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw JSON payloads from exchange.",
    )
    return parser.parse_args()


def _parse_symbols(text: str) -> Optional[List[str]]:
    symbols = [item.strip() for item in text.split(",") if item.strip()]
    return symbols or None


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _print_balances(balance: dict, min_balance: float) -> None:
    total = balance.get("total") or {}
    free = balance.get("free") or {}
    used = balance.get("used") or {}
    rows = []
    for currency, total_value in total.items():
        total_val = _safe_float(total_value) or 0.0
        if total_val < min_balance:
            continue
        rows.append(
            (
                currency,
                total_val,
                _safe_float(free.get(currency)) or 0.0,
                _safe_float(used.get(currency)) or 0.0,
            )
        )
    rows.sort(key=lambda item: item[1], reverse=True)

    print("Balances:")
    if not rows:
        print("  (no balances above threshold)")
        return
    for currency, total_val, free_val, used_val in rows:
        print(
            f"  {currency}: total={total_val:.8f} free={free_val:.8f} used={used_val:.8f}"
        )


def _position_size(pos: dict) -> Optional[float]:
    for key in ("contracts", "position", "size"):
        value = _safe_float(pos.get(key))
        if value is not None:
            return value
    info = pos.get("info") or {}
    return _safe_float(info.get("pos"))


def _position_side(pos: dict, size_val: Optional[float]) -> str:
    info = pos.get("info") or {}
    side = pos.get("side") or info.get("posSide")
    if side:
        return str(side).lower()
    if size_val is None:
        return "unknown"
    return "long" if size_val >= 0 else "short"


def _print_positions(positions: Iterable[dict]) -> None:
    rows = []
    for pos in positions:
        size_val = _position_size(pos)
        if size_val is None or abs(size_val) <= 0:
            continue
        info = pos.get("info") or {}
        entry = _safe_float(pos.get("entryPrice") or pos.get("avgPrice") or info.get("avgPx"))
        mark = _safe_float(pos.get("markPrice") or info.get("markPx"))
        unreal = _safe_float(pos.get("unrealizedPnl") or info.get("upl"))
        leverage = _safe_float(pos.get("leverage") or info.get("lever"))
        rows.append(
            {
                "symbol": pos.get("symbol") or info.get("instId"),
                "side": _position_side(pos, size_val),
                "size": abs(size_val),
                "entry": entry,
                "mark": mark,
                "unreal": unreal,
                "leverage": leverage,
            }
        )

    print("Positions:")
    if not rows:
        print("  (no open positions)")
        return
    for row in rows:
        print(
            "  {symbol} {side} size={size:.6f} entry={entry} mark={mark} "
            "upl={unreal} lev={leverage}".format(
                symbol=row["symbol"],
                side=row["side"],
                size=row["size"],
                entry=f"{row['entry']:.4f}" if row["entry"] is not None else "n/a",
                mark=f"{row['mark']:.4f}" if row["mark"] is not None else "n/a",
                unreal=f"{row['unreal']:.4f}" if row["unreal"] is not None else "n/a",
                leverage=f"{row['leverage']:.2f}" if row["leverage"] is not None else "n/a",
            )
        )


def main() -> None:
    args = parse_args()
    exchange = create_okx_client()
    exchange.load_markets()

    mode = "DEMO" if settings.okx_is_demo else "LIVE"
    print(f"OKX mode: {mode}")
    print(f"Default market: {settings.okx_default_market}")

    try:
        balance = exchange.fetch_balance()
    except Exception as exc:
        print(f"Balance fetch failed: {exc}")
        raise SystemExit(1)

    if args.raw:
        print("Balance raw:")
        print(json.dumps(balance, ensure_ascii=True, indent=2, default=str))
    _print_balances(balance, args.min_balance)

    if not exchange.has.get("fetchPositions", False):
        print("Positions: exchange does not support fetch_positions")
        return

    symbols = _parse_symbols(args.symbols)
    try:
        positions = exchange.fetch_positions(symbols) if symbols else exchange.fetch_positions()
    except Exception as exc:
        print(f"Position fetch failed: {exc}")
        raise SystemExit(1)

    if args.raw:
        print("Positions raw:")
        print(json.dumps(positions, ensure_ascii=True, indent=2, default=str))
    _print_positions(positions)


if __name__ == "__main__":
    main()
