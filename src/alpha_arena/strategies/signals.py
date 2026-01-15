"""Signal definitions for strategy outputs."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"


@dataclass(frozen=True)
class StrategySignal:
    strategy: str
    symbol: str
    timeframe: str
    signal_type: SignalType
    confidence: float
    timestamp: int
    price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size: Optional[float]
    leverage: Optional[int]
    reasoning: str
