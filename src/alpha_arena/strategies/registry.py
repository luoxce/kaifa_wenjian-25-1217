"""Strategy registry and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from alpha_arena.data import DataService
from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.bollinger_range import BollingerRangeStrategy
from alpha_arena.strategies.ema_trend import EMATrendStrategy
from alpha_arena.strategies.funding_rate_arbitrage import FundingRateArbitrageStrategy


StrategyFactory = Callable[[str, str, DataService, Optional[Dict]], BaseStrategy]


@dataclass(frozen=True)
class StrategySpec:
    key: str
    name: str
    enabled: bool
    implemented: bool
    description: str
    factory: Optional[StrategyFactory] = None
    regimes: tuple[str, ...] = ()


def _ema_factory(symbol: str, timeframe: str, ds: DataService, params: Optional[Dict]) -> BaseStrategy:
    return EMATrendStrategy(symbol, timeframe, ds, params=params)


def _bollinger_factory(
    symbol: str, timeframe: str, ds: DataService, params: Optional[Dict]
) -> BaseStrategy:
    return BollingerRangeStrategy(symbol, timeframe, ds, params=params)


def _funding_factory(
    symbol: str, timeframe: str, ds: DataService, params: Optional[Dict]
) -> BaseStrategy:
    return FundingRateArbitrageStrategy(symbol, timeframe, ds, params=params)


STRATEGY_SPECS: List[StrategySpec] = [
    StrategySpec(
        key="ema_trend",
        name="EMA Trend",
        enabled=True,
        implemented=True,
        description="EMA trend-following strategy",
        factory=_ema_factory,
        regimes=("TREND",),
    ),
    StrategySpec(
        key="bollinger_range",
        name="Bollinger Range",
        enabled=True,
        implemented=True,
        description="Bollinger band range strategy",
        factory=_bollinger_factory,
        regimes=("RANGE",),
    ),
    StrategySpec(
        key="funding_rate_arbitrage",
        name="Funding Rate Arbitrage",
        enabled=True,
        implemented=True,
        description="Funding rate arbitrage strategy",
        factory=_funding_factory,
        regimes=(),
    ),
    StrategySpec(
        key="breakout",
        name="Breakout",
        enabled=False,
        implemented=False,
        description="Key level / channel breakout strategy (planned)",
        factory=None,
        regimes=("BREAKOUT", "TREND"),
    ),
    StrategySpec(
        key="grid_trading",
        name="Grid Trading",
        enabled=False,
        implemented=False,
        description="Arithmetic / geometric / dynamic grid (planned)",
        factory=None,
        regimes=("RANGE",),
    ),
    StrategySpec(
        key="momentum",
        name="Momentum",
        enabled=False,
        implemented=False,
        description="Price/volume momentum strategy (planned)",
        factory=None,
        regimes=("TREND", "BREAKOUT"),
    ),
    StrategySpec(
        key="mean_reversion",
        name="Mean Reversion",
        enabled=False,
        implemented=False,
        description="RSI/std mean reversion strategy (planned)",
        factory=None,
        regimes=("RANGE",),
    ),
    StrategySpec(
        key="onchain_signal",
        name="Onchain Signal",
        enabled=False,
        implemented=False,
        description="Onchain inflow/outflow and whale monitoring (planned)",
        factory=None,
        regimes=("TREND", "BREAKOUT"),
    ),
    StrategySpec(
        key="time_cycle",
        name="Time Cycle",
        enabled=False,
        implemented=False,
        description="Funding window / weekend rules (planned)",
        factory=None,
        regimes=("RANGE",),
    ),
    StrategySpec(
        key="volatility",
        name="Volatility",
        enabled=False,
        implemented=False,
        description="Volatility breakout strategy (planned)",
        factory=None,
        regimes=("BREAKOUT",),
    ),
]


class StrategyLibrary:
    """Strategy registry with enable flags."""

    def __init__(self, data_service: DataService) -> None:
        self.data_service = data_service

    def list_all(self) -> List[StrategySpec]:
        return list(STRATEGY_SPECS)

    def list_enabled(self) -> List[StrategySpec]:
        return [spec for spec in STRATEGY_SPECS if spec.enabled]

    def get(self, key: str) -> Optional[StrategySpec]:
        for spec in STRATEGY_SPECS:
            if spec.key == key:
                return spec
        return None

    def build(
        self, key: str, symbol: str, timeframe: str, params: Optional[Dict] = None
    ) -> BaseStrategy:
        spec = self.get(key)
        if not spec:
            raise KeyError(f"Strategy not found: {key}")
        if not spec.implemented or not spec.factory:
            raise ValueError(f"Strategy not implemented: {key}")
        return spec.factory(symbol, timeframe, self.data_service, params)
