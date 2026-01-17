"""Hybrid decision system combining LLM constraints and RL optimization."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel, ValidationError

from alpha_arena.data.data_service import DataService

logger = logging.getLogger(__name__)


class DecisionMode(str, Enum):
    LLM_ONLY = "llm_only"
    RL_ONLY = "rl_only"
    HYBRID = "hybrid"
    SAFE_MODE = "safe_mode"


@dataclass
class MarketConstraints:
    max_position: float
    max_drawdown: float
    allowed_strategies: List[str]
    risk_level: str
    reason: str
    confidence: float


@dataclass
class RLAction:
    target_position: float
    strategy_weights: np.ndarray
    expected_return: float
    risk_score: float


class _ConstraintModel(BaseModel):
    max_position: float
    max_drawdown: float
    allowed_strategies: List[str]
    risk_level: str
    reason: str
    confidence: float


class HybridDecisionSystem:
    """Orchestrate LLM constraints and RL execution."""

    def __init__(
        self,
        data_service: Optional[DataService],
        llm_decision_maker,
        rl_decision_maker,
        portfolio_decision,
        mode: DecisionMode,
        symbol: str,
        timeframe: str,
    ) -> None:
        self.data_service = data_service or DataService()
        self.llm_decision_maker = llm_decision_maker
        self.rl_decision_maker = rl_decision_maker
        self.portfolio_decision = portfolio_decision
        self.mode = mode
        self.symbol = symbol
        self.timeframe = timeframe

        self.llm_calls = 0
        self.rl_calls = 0
        self.llm_interventions = 0
        self.total_cost = 0.0

        self._last_llm_analysis: Optional[datetime] = None
        self._last_constraints: Optional[MarketConstraints] = None
        self._analysis_interval = float(os.getenv("LLM_ANALYSIS_INTERVAL", "24"))
        self._intervention_enabled = os.getenv("LLM_INTERVENTION_ENABLED", "true").lower() == "true"

    def make_decision(self, limit: int) -> Optional[Dict]:
        if self.mode == DecisionMode.LLM_ONLY:
            return self._call_llm_strategy(limit)
        if self.mode == DecisionMode.RL_ONLY:
            base = self._call_portfolio(limit)
            if not base:
                return base
            return self._apply_rl(base, None)
        if self.mode == DecisionMode.SAFE_MODE:
            return self._safe_mode(limit)
        return self._hybrid_mode(limit)

    def _call_llm_strategy(self, limit: int) -> Optional[Dict]:
        if not self.llm_decision_maker:
            return None
        if hasattr(self.llm_decision_maker, "decide"):
            result = self.llm_decision_maker.decide(self.symbol, self.timeframe, limit=limit)
            return getattr(result, "__dict__", None) if result is not None else None
        if hasattr(self.llm_decision_maker, "select"):
            result = self.llm_decision_maker.select(self.symbol, self.timeframe, limit=limit)
            return getattr(result, "__dict__", None) if result is not None else None
        return None

    def _call_portfolio(self, limit: int) -> Optional[Dict]:
        if not self.portfolio_decision or not hasattr(self.portfolio_decision, "decide"):
            return None
        return self.portfolio_decision.decide(self.symbol, self.timeframe, limit=limit)

    def _hybrid_mode(self, limit: int) -> Optional[Dict]:
        constraints = self._maybe_run_llm_analysis(limit)
        base = self._call_portfolio(limit)
        if not base:
            return base

        rl_action = self._rl_optimize_with_constraints(base, constraints)
        rl_action = self._check_and_intervene(rl_action, base, constraints)
        return self._apply_rl(base, rl_action)

    def _safe_mode(self, limit: int) -> Optional[Dict]:
        constraints = self._maybe_run_llm_analysis(limit)
        base = self._call_portfolio(limit)
        if not base:
            return base
        rl_action = self._rl_optimize_with_constraints(base, constraints)
        if constraints.confidence < 0.5 or abs(rl_action.target_position) < 0.05:
            return self._hold_decision(base, reason="safe_mode_low_confidence")
        return self._apply_rl(base, rl_action)

    def _maybe_run_llm_analysis(self, limit: int) -> MarketConstraints:
        now = datetime.now(timezone.utc)
        if (
            self._last_llm_analysis is None
            or now - self._last_llm_analysis >= timedelta(hours=self._analysis_interval)
        ):
            self._last_constraints = self._llm_market_analysis(limit)
            self._last_llm_analysis = now
        if self._last_constraints is None:
            self._last_constraints = self._default_constraints()
        return self._last_constraints

    def _llm_market_analysis(self, limit: int) -> MarketConstraints:
        snapshot = self._market_snapshot(limit)
        system_prompt = (
            "You are a risk management expert for a quant trading system. "
            "Analyze the market snapshot and set trading constraints."
        )
        user_prompt = (
            "Market data: "
            f"price={snapshot['price']}, "
            f"return_pct={snapshot['return_pct']}, "
            f"funding_rate={snapshot['funding_rate']}, "
            f"volatility={snapshot['volatility']}. "
            "Return JSON: {max_position, max_drawdown, allowed_strategies, "
            "risk_level, reason, confidence}."
        )

        client = None
        if hasattr(self.llm_decision_maker, "llm_client"):
            client = self.llm_decision_maker.llm_client
        elif hasattr(self.llm_decision_maker, "chat_json"):
            client = self.llm_decision_maker

        if client is None:
            return self._default_constraints()

        try:
            self.llm_calls += 1
            response, _raw = client.chat_json(system_prompt, user_prompt, _ConstraintModel)
            return MarketConstraints(
                max_position=response.max_position,
                max_drawdown=response.max_drawdown,
                allowed_strategies=response.allowed_strategies,
                risk_level=response.risk_level,
                reason=response.reason,
                confidence=response.confidence,
            )
        except (ValidationError, Exception) as exc:
            logger.warning("LLM market analysis failed: %s", exc)
            return self._default_constraints()

    def _rl_optimize_with_constraints(
        self, portfolio_decision: Dict, constraints: Optional[MarketConstraints]
    ) -> RLAction:
        if not self.rl_decision_maker or not hasattr(self.rl_decision_maker, "get_rl_action"):
            return RLAction(
                target_position=0.0,
                strategy_weights=np.array([0.33, 0.33, 0.34], dtype=np.float32),
                expected_return=0.0,
                risk_score=1.0,
            )
        self.rl_calls += 1
        market_payload = self._build_market_payload(portfolio_decision)
        target_position, weights = self.rl_decision_maker.get_rl_action(market_payload)

        max_pos = constraints.max_position if constraints else 1.0
        target_position = float(np.clip(target_position, -max_pos, max_pos))

        allowed = constraints.allowed_strategies if constraints else []
        if allowed:
            mask = np.array(
                [
                    1.0 if "ema" in allowed or "ema_trend" in allowed else 0.0,
                    1.0 if "bollinger" in allowed or "bollinger_range" in allowed else 0.0,
                    1.0
                    if "funding" in allowed or "funding_rate_arbitrage" in allowed
                    else 0.0,
                ],
                dtype=np.float32,
            )
            weights = weights * mask
            total = float(weights.sum())
            if total > 0:
                weights = weights / total
        return RLAction(
            target_position=target_position,
            strategy_weights=weights.astype(np.float32),
            expected_return=0.0,
            risk_score=1.0 - (constraints.confidence if constraints else 0.5),
        )

    def _check_and_intervene(
        self, rl_action: RLAction, portfolio_decision: Dict, constraints: MarketConstraints
    ) -> RLAction:
        if not self._intervention_enabled:
            return rl_action
        issues = []
        max_pos = constraints.max_position if constraints else 1.0
        if max_pos > 0 and abs(rl_action.target_position) > 0.9 * max_pos:
            issues.append("position_near_limit")
        if rl_action.strategy_weights.size and np.max(rl_action.strategy_weights) > 0.8:
            issues.append("weight_concentration")
        original_signal = self._extract_original_signal(portfolio_decision)
        if abs(rl_action.target_position - original_signal) > 1.0:
            issues.append("signal_divergence")

        if issues and constraints.confidence < 0.8:
            self.llm_interventions += 1
            logger.warning("LLM intervention triggered: %s", ",".join(issues))
            rl_action = RLAction(
                target_position=rl_action.target_position * 0.5,
                strategy_weights=rl_action.strategy_weights,
                expected_return=rl_action.expected_return,
                risk_score=rl_action.risk_score,
            )
        return rl_action

    def _apply_rl(
        self, portfolio_decision: Dict, rl_action: Optional[RLAction]
    ) -> Dict:
        if rl_action is None:
            return portfolio_decision

        updated = dict(portfolio_decision)
        updated["rl_adjusted"] = True
        updated["rl_contribution"] = 0.5
        updated["target_position"] = rl_action.target_position
        updated["rl_suggestion"] = {
            "target_position": rl_action.target_position,
            "strategy_weights": rl_action.strategy_weights.tolist(),
            "expected_return": rl_action.expected_return,
            "risk_score": rl_action.risk_score,
        }
        updated["allocations"] = self._apply_weights_to_allocations(
            portfolio_decision.get("allocations", []), rl_action.strategy_weights
        )
        return updated

    def _apply_weights_to_allocations(self, allocations: List[Dict], weights: np.ndarray) -> List[Dict]:
        weight_map = {
            "ema_trend": float(weights[0]),
            "bollinger_range": float(weights[1]),
            "funding_rate_arbitrage": float(weights[2]),
        }
        updated = []
        for item in allocations:
            entry = dict(item)
            strategy_id = entry.get("strategy_id")
            if strategy_id in weight_map:
                entry["weight"] = weight_map[strategy_id]
            updated.append(entry)
        if not updated:
            for key, value in weight_map.items():
                updated.append({"strategy_id": key, "weight": value, "score": value})
        return updated

    def _hold_decision(self, base: Dict, reason: str) -> Dict:
        updated = dict(base)
        updated["rl_adjusted"] = False
        updated["reasoning"] = reason
        updated["allocations"] = []
        updated["target_position"] = 0.0
        return updated

    def _market_snapshot(self, limit: int) -> Dict[str, float]:
        candles = self.data_service.get_ohlcv(self.symbol, self.timeframe, limit=limit)
        if candles.empty:
            return {"price": 0.0, "return_pct": 0.0, "funding_rate": 0.0, "volatility": 0.0}
        candles = candles.reset_index(drop=True)
        close = candles["close"].astype(float)
        price = float(close.iloc[-1])
        return_pct = ((price - float(close.iloc[0])) / float(close.iloc[0])) * 100.0
        returns = close.pct_change().dropna()
        volatility = float(returns.std()) if not returns.empty else 0.0
        funding = self.data_service.get_latest_funding(self.symbol)
        funding_rate = float(funding.funding_rate) if funding else 0.0
        return {
            "price": price,
            "return_pct": return_pct,
            "funding_rate": funding_rate,
            "volatility": volatility,
        }

    def _default_constraints(self) -> MarketConstraints:
        return MarketConstraints(
            max_position=1.0,
            max_drawdown=0.2,
            allowed_strategies=["ema_trend", "bollinger_range", "funding_rate_arbitrage"],
            risk_level="medium",
            reason="default_constraints",
            confidence=0.5,
        )

    def _build_market_payload(self, portfolio_decision: Dict) -> Dict[str, float]:
        indicators = portfolio_decision.get("indicators", {}) or {}
        rsi = float(indicators.get("RSI") or 0.0)
        bb_width = float(indicators.get("BB_Width") or 0.0)
        macd = float(indicators.get("MACD") or 0.0)
        macd_signal = float(indicators.get("MACD_Signal") or 0.0)
        ema_signal = 1.0 if macd > macd_signal else -1.0 if macd < macd_signal else 0.0
        return {
            "rsi": rsi,
            "bb_position": 0.0,
            "bb_width": bb_width,
            "funding_rate": 0.0,
            "ema_signal": ema_signal,
            "bollinger_signal": 0.0,
            "funding_signal": 0.0,
            "regime": portfolio_decision.get("regime", "range"),
        }

    def _extract_original_signal(self, portfolio_decision: Dict) -> float:
        allocations = portfolio_decision.get("allocations", []) or []
        if not allocations:
            return 0.0
        weight_sum = sum(float(item.get("weight", 0.0)) for item in allocations)
        return max(0.0, min(weight_sum, 1.0))

    def get_performance_report(self) -> Dict[str, float]:
        return {
            "llm_calls": self.llm_calls,
            "rl_calls": self.rl_calls,
            "llm_interventions": self.llm_interventions,
            "total_cost": self.total_cost,
        }
