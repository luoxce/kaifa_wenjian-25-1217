"""Funding rate arbitrage strategy."""

from __future__ import annotations

from typing import Dict, List, Optional

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.signals import SignalType, StrategySignal


class FundingRateArbitrageStrategy(BaseStrategy):
    """Funding rate arbitrage strategy."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "min_funding_rate": 0.001,  # 0.1%
            "exit_funding_rate": 0.0005,  # 0.05%
            "max_position": 0.50,
            "max_leverage": 1,
            "min_duration": 3,
            "history_window": 10,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "funding_rate_arbitrage",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )
        self._funding_history: List[float] = []

    def generate_signal(self) -> StrategySignal:
        funding = self.data_service.get_latest_funding(self.symbol)
        if funding is None:
            return self._hold("no_funding_data")

        rate = float(funding.funding_rate)
        self._funding_history.append(rate)
        if len(self._funding_history) > self.params["history_window"]:
            self._funding_history.pop(0)

        price = 0.0
        ts = int(funding.timestamp)
        candles = self.get_candles()
        if not candles.empty:
            price = float(candles.iloc[-1]["close"])

        if rate >= self.params["min_funding_rate"]:
            if len(self._funding_history) >= self.params["min_duration"]:
                recent = self._funding_history[-self.params["min_duration"] :]
                if all(r >= self.params["min_funding_rate"] for r in recent):
                    return StrategySignal(
                        strategy=self.name,
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        signal_type=SignalType.BUY,
                        confidence=0.9,
                        timestamp=ts,
                        price=price,
                        stop_loss=None,
                        take_profit=None,
                        position_size=self.params["max_position"],
                        leverage=self.params["max_leverage"],
                        reasoning="Funding rate elevated for consecutive cycles.",
                    )

        if rate <= self.params["exit_funding_rate"]:
            return StrategySignal(
                strategy=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal_type=SignalType.CLOSE_LONG,
                confidence=0.8,
                timestamp=ts,
                price=price,
                stop_loss=None,
                take_profit=None,
                position_size=None,
                leverage=None,
                reasoning="Funding rate normalized; exit arbitrage.",
            )

        return self._hold("no_signal")

    def _hold(self, reason: str) -> StrategySignal:
        ts = 0
        price = 0.0
        funding = self.data_service.get_latest_funding(self.symbol)
        if funding:
            ts = int(funding.timestamp)
        candles = self.get_candles()
        if not candles.empty:
            price = float(candles.iloc[-1]["close"])
        return StrategySignal(
            strategy=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_type=SignalType.HOLD,
            confidence=0.0,
            timestamp=ts,
            price=price,
            stop_loss=None,
            take_profit=None,
            position_size=None,
            leverage=None,
            reasoning=reason,
        )
