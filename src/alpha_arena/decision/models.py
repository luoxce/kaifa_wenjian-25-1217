"""Decision models and schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"


class LLMDecision(BaseModel):
    market_regime: MarketRegime
    selected_strategy_id: str
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

    @field_validator("selected_strategy_id")
    @classmethod
    def _normalize_strategy(cls, value: str) -> str:
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
    confidence: Optional[float]
    reasoning: str
    raw_response: str
    system_prompt: str
    user_prompt: str
    indicators: Dict[str, Any]
    market_data: Dict[str, Any]
    accepted: bool
    rejection_reason: Optional[str]
