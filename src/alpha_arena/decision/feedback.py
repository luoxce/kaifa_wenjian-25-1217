"""Decision feedback analysis for LLM guidance."""

from __future__ import annotations

import json
from statistics import median
from typing import Dict, List, Optional, Tuple

from alpha_arena.data import DataService
from alpha_arena.data.health import timeframe_to_ms
from alpha_arena.db.connection import get_connection
from alpha_arena.strategies import StrategyLibrary


class DecisionFeedbackAnalyzer:
    """Analyze recent decisions against realized trade outcomes."""

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        strategy_library: Optional[StrategyLibrary] = None,
    ) -> None:
        self.data_service = data_service or DataService()
        self.strategy_library = strategy_library or StrategyLibrary(self.data_service)
        self._strategy_names = {
            spec.key: spec.name for spec in self.strategy_library.list_all()
        }

    def analyze_recent_decisions(self, limit: int = 20) -> Dict[str, object]:
        decisions = self._fetch_recent_decisions(limit)
        if not decisions:
            return {
                "limit": limit,
                "decisions": [],
                "strategy_stats": {},
                "regime_stats": {},
            }

        decisions_by_key = self._group_by_symbol_timeframe(decisions)
        trades_by_symbol = self._load_trades(decisions_by_key)

        strategy_stats: Dict[str, Dict[str, float]] = {}
        regime_stats: Dict[str, Dict[str, float]] = {}

        for (symbol, timeframe), items in decisions_by_key.items():
            interval_ms = _estimate_interval_ms(items, timeframe)
            trades = trades_by_symbol.get(symbol, [])
            for idx, decision in enumerate(items):
                start_ts = decision["timestamp"]
                end_ts = (
                    items[idx + 1]["timestamp"]
                    if idx + 1 < len(items)
                    else start_ts + interval_ms
                )
                pnl, notional = _aggregate_trades(trades, start_ts, end_ts)
                return_pct = (pnl / notional) if notional > 0 else 0.0
                decision["return_pct"] = return_pct
                decision["pnl"] = pnl
                decision["notional"] = notional
                decision["trade_count"] = 0 if notional == 0 else None
                if notional > 0:
                    decision["trade_count"] = sum(
                        1
                        for trade in trades
                        if start_ts <= trade["timestamp"] < end_ts
                        and trade["price"] is not None
                        and trade["amount"] is not None
                    )

                if notional <= 0:
                    continue

                win = return_pct > 0
                for alloc in decision["allocations"]:
                    weight = alloc["weight"]
                    strategy_id = alloc["strategy_id"]
                    stats = strategy_stats.setdefault(
                        strategy_id, {"wins": 0.0, "total": 0.0, "return_sum": 0.0}
                    )
                    stats["wins"] += weight if win else 0.0
                    stats["total"] += weight
                    stats["return_sum"] += return_pct * weight

                regime = decision.get("market_regime")
                if regime:
                    stats = regime_stats.setdefault(
                        regime, {"wins": 0, "total": 0, "return_sum": 0.0}
                    )
                    stats["wins"] += 1 if win else 0
                    stats["total"] += 1
                    stats["return_sum"] += return_pct

        return {
            "limit": limit,
            "decisions": decisions,
            "strategy_stats": _finalize_stats(strategy_stats),
            "regime_stats": _finalize_stats(regime_stats),
        }

    def generate_feedback_summary(self, limit: int = 20) -> str:
        analysis = self.analyze_recent_decisions(limit=limit)
        strategy_stats = analysis.get("strategy_stats", {})
        regime_stats = analysis.get("regime_stats", {})
        if not strategy_stats:
            return (
                f"\u6700\u8fd1{limit}\u6b21\u51b3\u7b56\u7edf\u8ba1\uFF1A"
                "\u6682\u65E0\u6709\u6548\u4EA4\u6613\u7ED3\u679C"
            )

        lines = [f"\u6700\u8fd1{limit}\u6b21\u51b3\u7b56\u7edf\u8ba1\uFF1A"]
        for strategy_id, stats in _sorted_stats(strategy_stats):
            name = self._strategy_names.get(strategy_id, strategy_id)
            win_rate = stats["win_rate"] * 100
            avg_return = stats["avg_return"] * 100
            sign = "+" if avg_return >= 0 else ""
            lines.append(
                f"- {name}\uFF1A\u80DC\u7387{win_rate:.0f}%, "
                f"\u5E73\u5747\u6536\u76CA{sign}{avg_return:.2f}%"
            )

        best_strategy = _pick_best(strategy_stats)
        worst_strategy = _pick_worst(strategy_stats)
        if best_strategy:
            lines.append(
                "\u8868\u73B0\u6700\u597D\u7684\u7B56\u7565\uFF1A"
                f"{self._strategy_names.get(best_strategy[0], best_strategy[0])}"
                f"\uFF08\u80DC\u7387{best_strategy[1]['win_rate'] * 100:.0f}%\uFF09"
            )
        if worst_strategy:
            lines.append(
                "\u8868\u73B0\u6700\u5DEE\u7684\u7B56\u7565\uFF1A"
                f"{self._strategy_names.get(worst_strategy[0], worst_strategy[0])}"
                f"\uFF08\u80DC\u7387{worst_strategy[1]['win_rate'] * 100:.0f}%\uFF09"
            )

        if regime_stats:
            best_regime = _pick_best(regime_stats)
            worst_regime = _pick_worst(regime_stats)
            if best_regime:
                lines.append(
                    "\u8868\u73B0\u6700\u597D\u7684\u5E02\u573A\u73AF\u5883\uFF1A"
                    f"{best_regime[0]}\uFF08\u80DC\u7387{best_regime[1]['win_rate'] * 100:.0f}%\uFF09"
                )
            if worst_regime:
                lines.append(
                    "\u8868\u73B0\u6700\u5DEE\u7684\u5E02\u573A\u73AF\u5883\uFF1A"
                    f"{worst_regime[0]}\uFF08\u80DC\u7387{worst_regime[1]['win_rate'] * 100:.0f}%\uFF09"
                )

        return "\n".join(lines)

    def _fetch_recent_decisions(self, limit: int) -> List[Dict[str, object]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, timeframe, timestamp, action, confidence, technical_analysis
                FROM decisions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        decisions: List[Dict[str, object]] = []
        for row in rows:
            technical = _safe_json(row["technical_analysis"])
            allocations = _extract_allocations(row["action"], technical)
            decisions.append(
                {
                    "id": row["id"],
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "timestamp": int(row["timestamp"]),
                    "action": row["action"],
                    "confidence": row["confidence"],
                    "market_regime": technical.get("market_regime")
                    or technical.get("regime"),
                    "allocations": allocations,
                }
            )
        decisions.sort(key=lambda item: item["timestamp"])
        return decisions

    def _group_by_symbol_timeframe(
        self, decisions: List[Dict[str, object]]
    ) -> Dict[Tuple[str, str], List[Dict[str, object]]]:
        grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = {}
        for decision in decisions:
            key = (decision["symbol"], decision["timeframe"])
            grouped.setdefault(key, []).append(decision)
        for key in grouped:
            grouped[key].sort(key=lambda item: item["timestamp"])
        return grouped

    def _load_trades(
        self, decisions_by_key: Dict[Tuple[str, str], List[Dict[str, object]]]
    ) -> Dict[str, List[Dict[str, object]]]:
        symbols = {symbol for symbol, _ in decisions_by_key.keys()}
        if not symbols:
            return {}

        min_ts = min(
            decision["timestamp"]
            for items in decisions_by_key.values()
            for decision in items
        )
        max_ts = max(
            decision["timestamp"]
            for items in decisions_by_key.values()
            for decision in items
        )
        fallback_interval = max(
            _estimate_interval_ms(items, timeframe)
            for (symbol, timeframe), items in decisions_by_key.items()
        )
        end_ts = max_ts + fallback_interval

        placeholders = ",".join("?" for _ in symbols)
        params = list(symbols) + [int(min_ts), int(end_ts)]
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT symbol, price, amount, realized_pnl, timestamp
                FROM trades
                WHERE symbol IN ({placeholders})
                  AND timestamp >= ?
                  AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                params,
            ).fetchall()

        trades_by_symbol: Dict[str, List[Dict[str, object]]] = {s: [] for s in symbols}
        for row in rows:
            trades_by_symbol.setdefault(row["symbol"], []).append(
                {
                    "symbol": row["symbol"],
                    "price": row["price"],
                    "amount": row["amount"],
                    "realized_pnl": row["realized_pnl"],
                    "timestamp": int(row["timestamp"]),
                }
            )
        return trades_by_symbol


def _estimate_interval_ms(items: List[Dict[str, object]], timeframe: str) -> int:
    diffs = []
    for idx in range(len(items) - 1):
        delta = items[idx + 1]["timestamp"] - items[idx]["timestamp"]
        if delta > 0:
            diffs.append(delta)
    if diffs:
        return int(median(diffs))
    try:
        return int(timeframe_to_ms(timeframe))
    except Exception:
        return 60 * 60 * 1000


def _aggregate_trades(
    trades: List[Dict[str, object]], start_ts: int, end_ts: int
) -> Tuple[float, float]:
    pnl = 0.0
    notional = 0.0
    for trade in trades:
        ts = trade["timestamp"]
        if ts < start_ts or ts >= end_ts:
            continue
        price = trade["price"]
        amount = trade["amount"]
        if price is None or amount is None:
            continue
        try:
            notional += abs(float(price) * float(amount))
        except (TypeError, ValueError):
            continue
        pnl_val = trade.get("realized_pnl")
        try:
            pnl += float(pnl_val) if pnl_val is not None else 0.0
        except (TypeError, ValueError):
            continue
    return pnl, notional


def _safe_json(value: Optional[str]) -> Dict[str, object]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}


def _extract_allocations(action: Optional[str], technical: Dict[str, object]) -> List[Dict[str, float]]:
    allocations = technical.get("strategy_allocations")
    if isinstance(allocations, list):
        return _normalize_allocations(allocations)

    allocations = technical.get("allocations")
    if isinstance(allocations, list):
        return _normalize_allocations(allocations)

    selected = technical.get("selected_strategy_id") or action
    if not selected or str(selected).upper() == "HOLD":
        return []
    return [{"strategy_id": str(selected), "weight": 1.0}]


def _normalize_allocations(raw: List[Dict[str, object]]) -> List[Dict[str, float]]:
    cleaned: List[Dict[str, float]] = []
    for item in raw:
        strategy_id = item.get("strategy_id") or item.get("id")
        weight = item.get("weight")
        try:
            weight_val = float(weight)
        except (TypeError, ValueError):
            continue
        if not strategy_id or weight_val <= 0:
            continue
        cleaned.append({"strategy_id": str(strategy_id), "weight": weight_val})
    total = sum(item["weight"] for item in cleaned)
    if total <= 0:
        return []
    for item in cleaned:
        item["weight"] = item["weight"] / total
    return cleaned


def _finalize_stats(stats: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    output: Dict[str, Dict[str, float]] = {}
    for key, values in stats.items():
        total = values.get("total", 0.0)
        if total <= 0:
            continue
        win_rate = values.get("wins", 0.0) / total
        avg_return = values.get("return_sum", 0.0) / total
        output[key] = {
            "wins": values.get("wins", 0.0),
            "total": total,
            "win_rate": win_rate,
            "avg_return": avg_return,
        }
    return output


def _sorted_stats(stats: Dict[str, Dict[str, float]]) -> List[Tuple[str, Dict[str, float]]]:
    return sorted(stats.items(), key=lambda item: item[1].get("avg_return", 0.0), reverse=True)


def _pick_best(stats: Dict[str, Dict[str, float]]) -> Optional[Tuple[str, Dict[str, float]]]:
    if not stats:
        return None
    return max(stats.items(), key=lambda item: item[1].get("win_rate", 0.0))


def _pick_worst(stats: Dict[str, Dict[str, float]]) -> Optional[Tuple[str, Dict[str, float]]]:
    if not stats:
        return None
    return min(stats.items(), key=lambda item: item[1].get("win_rate", 0.0))
