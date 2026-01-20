"""Decision models and schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"
    STRONG_TREND = "STRONG_TREND"
    WEAK_TREND = "WEAK_TREND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"


class StrategyAllocation(BaseModel):
    strategy_id: str
    weight: float
    confidence: float
    reasoning: str

    @field_validator("strategy_id")
    @classmethod
    def _normalize_strategy(cls, value: str) -> str:
        if value is None:
            raise ValueError("strategy_id is required")
        normalized = value.strip()
        if normalized.upper() == "HOLD":
            return "HOLD"
        return normalized.lower()

    @field_validator("weight")
    @classmethod
    def _check_weight(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("weight must be between 0 and 1")
        return value

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value

    @field_validator("reasoning")
    @classmethod
    def _normalize_reasoning(cls, value: str) -> str:
        return value.strip()


class LLMDecision(BaseModel):
    market_regime: MarketRegime
    strategy_allocations: List[StrategyAllocation] = Field(default_factory=list)
    total_position: Optional[float] = None
    selected_strategy_id: Optional[str] = None
    confidence: float
    reasoning: str

    @field_validator("market_regime", mode="before")
    @classmethod
    def _normalize_regime(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value

    @field_validator("total_position")
    @classmethod
    def _check_total_position(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if value < -1 or value > 1:
            raise ValueError("total_position must be between -1 and 1")
        return value

    @field_validator("selected_strategy_id")
    @classmethod
    def _normalize_strategy(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if normalized.upper() == "HOLD":
            return "HOLD"
        return normalized.lower()


@dataclass
class DecisionResult:
    symbol: str
    timeframe: str
    timestamp: int
    market_regime: Optional[str]
    selected_strategy_id: Optional[str]
    strategy_allocations: List[StrategyAllocation]
    total_position: Optional[float]
    confidence: Optional[float]
    reasoning: str
    raw_response: str
    system_prompt: str
    user_prompt: str
    indicators: Dict[str, Any]
    market_data: Dict[str, Any]
    accepted: bool
    rejection_reason: Optional[str]
