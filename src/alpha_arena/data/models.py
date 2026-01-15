"""Data layer models for normalized market snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd


@dataclass(frozen=True)
class FundingSnapshot:
    symbol: str
    timestamp: int
    funding_rate: float
    next_funding_time: Optional[int]


@dataclass(frozen=True)
class PriceSnapshot:
    symbol: str
    timestamp: int
    last: Optional[float]
    mark: Optional[float]
    index: Optional[float]


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    candles: "pd.DataFrame"
    funding: Optional[FundingSnapshot]
    prices: Optional[PriceSnapshot]


@dataclass(frozen=True)
class DecisionRecord:
    symbol: str
    timeframe: str
    timestamp: int
    action: str
    confidence: Optional[float]
    reasoning: str
    technical_analysis: Optional[str]
    risk_assessment: Optional[str]
    llm_response: Optional[str]
    llm_run_id: Optional[int] = None
    prompt_version_id: Optional[int] = None
    model_version_id: Optional[int] = None
