"""LLM strategy selector."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.decision.llm_client import LLMClient
from alpha_arena.decision.models import DecisionResult, LLMDecision
from alpha_arena.decision.prompt_builder import PromptBuilder
from alpha_arena.strategies import StrategyLibrary
from alpha_arena.strategies.indicators import adx, bollinger_bands, macd, rsi


class LLMStrategySelector:
    """Select an active strategy via LLM and enforce safety checks."""

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        strategy_library: Optional[StrategyLibrary] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_client: Optional[LLMClient] = None,
        min_confidence: Optional[float] = None,
    ) -> None:
        self.data_service = data_service or DataService()
        self.strategy_library = strategy_library or StrategyLibrary(self.data_service)
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_client = llm_client or LLMClient()
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
        indicators = self._build_indicators(candles)
        active_strategies = self._get_active_strategies()

        prompts = self.prompt_builder.build(market_data, indicators, active_strategies)
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

        last = df.iloc[-1]
        return {
            "ADX": _safe_float(last["adx"]),
            "RSI": _safe_float(last["rsi"]),
            "BB_Width": _safe_float(last["bb_width"]),
            "MACD": _safe_float(last["macd"]),
            "MACD_Signal": _safe_float(last["macd_signal"]),
            "MACD_Hist": _safe_float(last["macd_hist"]),
        }

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
        selected = decision.selected_strategy_id
        accepted = True
        rejection_reason = None

        if selected == "HOLD":
            accepted = True
            rejection_reason = None
        elif selected not in active_ids:
            accepted = False
            rejection_reason = "unknown_strategy"
        elif decision.confidence < self.min_confidence:
            accepted = False
            rejection_reason = "low_confidence"

        return DecisionResult(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=market_data["timestamp"],
            market_regime=decision.market_regime.value,
            selected_strategy_id=selected,
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
