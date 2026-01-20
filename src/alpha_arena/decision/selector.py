"""LLM strategy selector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.decision.feedback import DecisionFeedbackAnalyzer
from alpha_arena.decision.llm_client import LLMClient
from alpha_arena.decision.models import DecisionResult, LLMDecision, StrategyAllocation
from alpha_arena.decision.portfolio import compute_regime_context
from alpha_arena.decision.prompt_builder import PromptBuilder
from alpha_arena.strategies import StrategyLibrary
from alpha_arena.strategies.indicators import (
    adx,
    atr_percentile,
    bollinger_bands,
    macd,
    price_efficiency,
    rsi,
    volume_trend,
)


class LLMStrategySelector:
    """Select an active strategy via LLM and enforce safety checks."""

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        strategy_library: Optional[StrategyLibrary] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_client: Optional[LLMClient] = None,
        feedback_analyzer: Optional[DecisionFeedbackAnalyzer] = None,
        min_confidence: Optional[float] = None,
    ) -> None:
        self.data_service = data_service or DataService()
        self.strategy_library = strategy_library or StrategyLibrary(self.data_service)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_client = llm_client or LLMClient()
        self.feedback_analyzer = feedback_analyzer or DecisionFeedbackAnalyzer(
            self.data_service, self.strategy_library
        )
        self.min_confidence = (
            min_confidence if min_confidence is not None else settings.risk_min_confidence
        )
        self.last_result: Optional[DecisionResult] = None

    def select(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> Optional[DecisionResult]:
        candles = self.data_service.get_ohlcv(symbol, timeframe, limit=limit)
        if candles.empty:
            self.last_result = DecisionResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=0,
                market_regime=None,
                selected_strategy_id=None,
                strategy_allocations=[],
                total_position=None,
                confidence=None,
                reasoning="no_candles",
                raw_response="",
                system_prompt="",
                user_prompt="",
                indicators={},
                market_data={},
                accepted=False,
                rejection_reason="no_candles",
            )
            return None

        market_data = self._build_market_data(symbol, timeframe, candles)
        regime_context = self._build_regime_context(candles)
        indicators = regime_context.get("indicators") or self._build_indicators(candles)
        active_strategies = self._get_active_strategies()

        feedback_summary = self._build_feedback_summary(limit=20)
        prompts = self.prompt_builder.build(
            market_data,
            indicators,
            active_strategies,
            regime_context=regime_context,
            decision_feedback=feedback_summary,
        )
        try:
            decision, raw = self.llm_client.chat_json(
                prompts.system, prompts.user, LLMDecision
            )
        except Exception as exc:
            self.last_result = DecisionResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=market_data["timestamp"],
                market_regime=None,
                selected_strategy_id=None,
                strategy_allocations=[],
                total_position=None,
                confidence=None,
                reasoning="llm_error",
                raw_response=str(exc),
                system_prompt=prompts.system,
                user_prompt=prompts.user,
                indicators=indicators,
                market_data=market_data,
                accepted=False,
                rejection_reason="llm_error",
            )
            return None

        decision_result = self._validate_decision(
            symbol, timeframe, market_data, indicators, prompts, decision, raw
        )
        self.last_result = decision_result
        return decision_result if decision_result.accepted else None

    def _build_market_data(
        self, symbol: str, timeframe: str, candles: pd.DataFrame
    ) -> Dict[str, Any]:
        last = candles.iloc[-1]
        last_price = float(last["close"])
        last_volume = float(last["volume"])
        ohlcv_tail = (
            candles.tail(5)[["timestamp", "open", "high", "low", "close", "volume"]]
            .to_dict(orient="records")
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": int(last["timestamp"]),
            "last_price": last_price,
            "last_volume": last_volume,
            "ohlcv_tail": ohlcv_tail,
        }

    def _build_indicators(self, candles: pd.DataFrame) -> Dict[str, Any]:
        df = candles.copy()
        df["rsi"] = rsi(df["close"], 14)
        df["adx"] = adx(df, 14)
        macd_df = macd(df["close"])
        df["macd"] = macd_df["macd"]
        df["macd_signal"] = macd_df["signal"]
        df["macd_hist"] = macd_df["hist"]
        bb = bollinger_bands(df["close"])
        df["bb_width"] = bb["bandwidth"]
        df["bb_width_ma"] = df["bb_width"].rolling(window=20).mean()
        df["bb_width_ratio"] = df["bb_width"] / df["bb_width_ma"].replace(0, pd.NA)
        df["atr_percentile"] = atr_percentile(df, period=14, lookback=100)
        df["price_efficiency"] = price_efficiency(df, period=20)
        df["volume_trend"] = volume_trend(df, period=20)

        last = df.iloc[-1]
        return {
            "ADX": _safe_float(last["adx"]),
            "RSI": _safe_float(last["rsi"]),
            "BB_Width": _safe_float(last["bb_width"]),
            "BB_Width_Ratio": _safe_float(last["bb_width_ratio"]),
            "MACD": _safe_float(last["macd"]),
            "MACD_Signal": _safe_float(last["macd_signal"]),
            "MACD_Hist": _safe_float(last["macd_hist"]),
            "ATR_Percentile": _safe_float(last["atr_percentile"]),
            "Price_Efficiency": _safe_float(last["price_efficiency"]),
            "Volume_Trend": _safe_float(last["volume_trend"]),
        }

    def _build_regime_context(self, candles: pd.DataFrame) -> Dict[str, Any]:
        try:
            return compute_regime_context(candles, history_len=5)
        except Exception:
            return {"current": "UNKNOWN", "history": [], "signals": {}, "indicators": {}}

    def _build_feedback_summary(self, limit: int = 20) -> Optional[str]:
        try:
            return self.feedback_analyzer.generate_feedback_summary(limit=limit)
        except Exception:
            return None

    def _get_active_strategies(self) -> List[Dict[str, str]]:
        return [
            {
                "id": spec.key,
                "name": spec.name,
                "description": spec.description,
            }
            for spec in self.strategy_library.list_enabled()
        ]

    def _validate_decision(
        self,
        symbol: str,
        timeframe: str,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
        prompts,
        decision: LLMDecision,
        raw_response: str,
    ) -> DecisionResult:
        active_ids = {item["id"] for item in self._get_active_strategies()}
        allocations = list(decision.strategy_allocations or [])
        selected = decision.selected_strategy_id
        total_position = decision.total_position
        accepted = True
        rejection_reason = None
        max_abs_position = max(0.0, min(1.0, settings.portfolio_global_leverage))

        if allocations:
            invalid_ids = [
                alloc.strategy_id for alloc in allocations if alloc.strategy_id not in active_ids
            ]
            if invalid_ids and accepted:
                accepted = False
                rejection_reason = "unknown_strategy"
            weight_sum = sum(alloc.weight for alloc in allocations)
            if not (0.95 <= weight_sum <= 1.05) and accepted:
                accepted = False
                rejection_reason = "weight_sum_mismatch"
            if weight_sum <= 0 and accepted:
                accepted = False
                rejection_reason = "weight_sum_zero"
            if decision.confidence < self.min_confidence and accepted:
                accepted = False
                rejection_reason = "low_confidence"
            if total_position is None:
                total_position = max_abs_position
            if abs(total_position) > max_abs_position and accepted:
                accepted = False
                rejection_reason = "position_limit"
            selected = max(allocations, key=lambda item: item.weight).strategy_id
        else:
            if selected == "HOLD":
                allocations = []
                total_position = 0.0
                accepted = True
                rejection_reason = None
            elif selected is None:
                if total_position is None or abs(total_position) <= 1e-6:
                    selected = "HOLD"
                    allocations = []
                    total_position = 0.0
                    accepted = True
                    rejection_reason = None
                else:
                    accepted = False
                    rejection_reason = "missing_strategy"
            elif selected not in active_ids:
                accepted = False
                rejection_reason = "unknown_strategy"
            elif decision.confidence < self.min_confidence:
                accepted = False
                rejection_reason = "low_confidence"
            else:
                allocations = [
                    StrategyAllocation(
                        strategy_id=selected,
                        weight=1.0,
                        confidence=decision.confidence,
                        reasoning=decision.reasoning,
                    )
                ]
                if total_position is None:
                    total_position = max_abs_position
                if abs(total_position) > max_abs_position:
                    accepted = False
                    rejection_reason = "position_limit"

        return DecisionResult(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=market_data["timestamp"],
            market_regime=decision.market_regime.value,
            selected_strategy_id=selected,
            strategy_allocations=allocations,
            total_position=total_position,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            raw_response=raw_response,
            system_prompt=prompts.system,
            user_prompt=prompts.user,
            indicators=indicators,
            market_data=market_data,
            accepted=accepted,
            rejection_reason=rejection_reason,
        )


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
