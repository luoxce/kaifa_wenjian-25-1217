"""Strategy exports."""

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.bollinger_range import BollingerRangeStrategy
from alpha_arena.strategies.ema_trend import EMATrendStrategy
from alpha_arena.strategies.funding_rate_arbitrage import FundingRateArbitrageStrategy
from alpha_arena.strategies.registry import StrategyLibrary, StrategySpec
from alpha_arena.strategies.signals import SignalType, StrategySignal

__all__ = [
    "BaseStrategy",
    "BollingerRangeStrategy",
    "EMATrendStrategy",
    "FundingRateArbitrageStrategy",
    "StrategyLibrary",
    "StrategySpec",
    "SignalType",
    "StrategySignal",
]
