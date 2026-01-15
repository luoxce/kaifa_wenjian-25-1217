"""Multi-strategy scoring and portfolio allocation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Dict, List, Optional, Tuple

import pandas as pd

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.db.connection import get_connection
from alpha_arena.strategies import StrategyLibrary
from alpha_arena.strategies.indicators import adx, bollinger_bands, macd, rsi


@dataclass
class StrategyAllocation:
    strategy_id: str
    score: float
    weight: float
    regime_score: float
    performance_score: float
    notes: str


@dataclass
class PortfolioDecision:
    symbol: str
    timeframe: str
    timestamp: int
    regime: str
    allocations: List[StrategyAllocation]
    indicators: Dict[str, float]
    market_data: Dict[str, float]
    reasoning: str


class RegimeClassifier:
    """Classify market regime using simple indicator thresholds."""

    def __init__(
        self,
        adx_threshold: Optional[float] = None,
        bb_width_threshold: Optional[float] = None,
    ) -> None:
        self.adx_threshold = (
            adx_threshold if adx_threshold is not None else settings.regime_adx_threshold
        )
        self.bb_width_threshold = (
            bb_width_threshold
            if bb_width_threshold is not None
            else settings.regime_bb_width_threshold
        )

    def classify(self, indicators: Dict[str, float]) -> str:
        adx_val = indicators.get("ADX") or 0.0
        bb_width = indicators.get("BB_Width") or 0.0
        if adx_val >= self.adx_threshold:
            return "TREND"
        if bb_width <= self.bb_width_threshold:
            return "RANGE"
        return "BREAKOUT"


class StrategyPerformanceRepository:
    """Load historical performance per strategy from backtest tables."""

    def __init__(self, limit: int = 50) -> None:
        self.limit = limit

    def load_scores(self, symbol: str, timeframe: str) -> Dict[str, float]:
        rows = self._fetch_rows(symbol, timeframe)
        if not rows:
            return {}
        metrics: Dict[str, List[Tuple[float, float, float]]] = {}
        for row in rows:
            key = row["strategy_key"]
            if not key:
                continue
            metrics.setdefault(key, []).append(
                (
                    row.get("win_rate") or 0.0,
                    row.get("total_return") or 0.0,
                    row.get("max_drawdown") or 0.0,
                )
            )
        return {key: _aggregate_score(values) for key, values in metrics.items()}

    def _fetch_rows(self, symbol: str, timeframe: str) -> List[Dict[str, float]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT r.total_return, r.max_drawdown, r.win_rate, c.strategy_params
                FROM backtest_results r
                JOIN backtest_configs c ON r.config_id = c.id
                WHERE c.symbol = ? AND c.timeframe = ?
                ORDER BY r.id DESC
                LIMIT ?
                """,
                (symbol, timeframe, self.limit),
            ).fetchall()
        output: List[Dict[str, float]] = []
        for row in rows:
            params = row["strategy_params"]
            strategy_key = _extract_strategy_key(params)
            output.append(
                {
                    "strategy_key": strategy_key,
                    "win_rate": row["win_rate"],
                    "total_return": row["total_return"],
                    "max_drawdown": row["max_drawdown"],
                }
            )
        return output


class StrategyScorer:
    """Combine regime fit and historical performance into a final score."""

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        strategy_library: Optional[StrategyLibrary] = None,
        performance_repo: Optional[StrategyPerformanceRepository] = None,
        regime_classifier: Optional[RegimeClassifier] = None,
    ) -> None:
        self.data_service = data_service or DataService()
        self.strategy_library = strategy_library or StrategyLibrary(self.data_service)
        self.performance_repo = performance_repo or StrategyPerformanceRepository()
        self.regime_classifier = regime_classifier or RegimeClassifier()

    def score(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> Tuple[List[StrategyAllocation], PortfolioDecision]:
        candles = self.data_service.get_ohlcv(symbol, timeframe, limit=limit)
        if candles.empty:
            return [], PortfolioDecision(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=0,
                regime="UNKNOWN",
                allocations=[],
                indicators={},
                market_data={},
                reasoning="no_candles",
            )

        indicators = _compute_indicators(candles)
        regime = self.regime_classifier.classify(indicators)
        market_data = {
            "last_price": float(candles.iloc[-1]["close"]),
            "timestamp": int(candles.iloc[-1]["timestamp"]),
        }
        perf_scores = self.performance_repo.load_scores(symbol, timeframe)

        allocations: List[StrategyAllocation] = []
        for spec in self.strategy_library.list_enabled():
            regime_score = _regime_score(regime, spec.regimes)
            perf_score = perf_scores.get(spec.key, 0.5)
            final_score = 0.6 * regime_score + 0.4 * perf_score
            allocations.append(
                StrategyAllocation(
                    strategy_id=spec.key,
                    score=final_score,
                    weight=0.0,
                    regime_score=regime_score,
                    performance_score=perf_score,
                    notes=f"regime={regime}, base={regime_score:.2f}, perf={perf_score:.2f}",
                )
            )

        allocations.sort(key=lambda item: item.score, reverse=True)
        decision = PortfolioDecision(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=market_data["timestamp"],
            regime=regime,
            allocations=allocations,
            indicators=indicators,
            market_data=market_data,
            reasoning="scored_by_regime_and_performance",
        )
        return allocations, decision


class PortfolioScheduler:
    """Pick top-N strategies and normalize weights."""

    def __init__(self, top_n: int = 3, min_score: float = 0.45) -> None:
        self.top_n = top_n
        self.min_score = min_score

    def allocate(self, allocations: List[StrategyAllocation]) -> List[StrategyAllocation]:
        filtered = [item for item in allocations if item.score >= self.min_score]
        if not filtered:
            return []
        selected = filtered[: self.top_n]
        total = sum(item.score for item in selected) or 1.0
        for item in selected:
            item.weight = item.score / total
        return selected


def _compute_indicators(candles: pd.DataFrame) -> Dict[str, float]:
    df = candles.copy()
    df["rsi"] = rsi(df["close"], 14)
    df["adx"] = adx(df, 14)
    macd_df = macd(df["close"])
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["signal"]
    df["macd_hist"] = macd_df["hist"]
    bb = bollinger_bands(df["close"])
    df["bb_width"] = bb["bandwidth"]
    last = df.iloc[-1]
    return {
        "ADX": _safe_float(last["adx"]),
        "RSI": _safe_float(last["rsi"]),
        "BB_Width": _safe_float(last["bb_width"]),
        "MACD": _safe_float(last["macd"]),
        "MACD_Signal": _safe_float(last["macd_signal"]),
        "MACD_Hist": _safe_float(last["macd_hist"]),
    }


def _safe_float(value: object) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _regime_score(regime: str, regimes: Tuple[str, ...]) -> float:
    if not regimes:
        return 0.6
    if regime in regimes:
        return 1.0
    return 0.3


def _extract_strategy_key(params: object) -> str:
    if not params:
        return ""
    try:
        data = json.loads(params)
    except (TypeError, json.JSONDecodeError):
        return ""
    return (
        data.get("strategy_key")
        or data.get("strategy")
        or data.get("strategy_name")
        or ""
    )


def _aggregate_score(values: List[Tuple[float, float, float]]) -> float:
    if not values:
        return 0.5
    win_rates = [v[0] or 0.0 for v in values]
    returns = [v[1] or 0.0 for v in values]
    drawdowns = [v[2] or 0.0 for v in values]

    win_rate_score = max(min(sum(win_rates) / len(win_rates), 100.0), 0.0) / 100.0
    avg_return = sum(returns) / len(returns)
    return_score = (max(min(avg_return, 100.0), -100.0) / 200.0) + 0.5
    avg_drawdown = max(min(sum(drawdowns) / len(drawdowns), 100.0), 0.0)
    drawdown_score = 1.0 - avg_drawdown / 100.0

    return 0.5 * win_rate_score + 0.3 * return_score + 0.2 * drawdown_score
