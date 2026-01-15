"""Bollinger range strategy."""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import bollinger_bands, rsi
from alpha_arena.strategies.signals import SignalType, StrategySignal


class BollingerRangeStrategy(BaseStrategy):
    """Bollinger band ranging strategy."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_oversold": 35,
            "rsi_overbought": 65,
            "bandwidth_max": 0.04,
            "touch_threshold": 1.005,
            "stop_loss_pct": 0.02,
            "max_position": 0.25,
            "max_leverage": 2,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "bollinger_range",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )

    def generate_signal(self) -> StrategySignal:
        df = self.get_candles()
        if df.empty or len(df) < self.params["bb_period"] + 5:
            return self._hold("not_enough_data")

        df = df.copy()
        bands = bollinger_bands(
            df["close"], self.params["bb_period"], self.params["bb_std"]
        )
        df = df.join(bands)
        df["rsi"] = rsi(df["close"], 14)

        last = df.iloc[-1]
        price = float(last["close"])
        ts = int(last["timestamp"])
        bandwidth = float(last["bandwidth"]) if pd.notna(last["bandwidth"]) else 1.0
        rsi_val = float(last["rsi"])

        if bandwidth > self.params["bandwidth_max"]:
            return self._hold("bandwidth_too_wide")

        lower = float(last["lower"])
        upper = float(last["upper"])
        mid = float(last["mid"])

        if price <= lower * self.params["touch_threshold"] and rsi_val < self.params[
            "rsi_oversold"
        ]:
            return StrategySignal(
                strategy=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal_type=SignalType.BUY,
                confidence=0.75,
                timestamp=ts,
                price=price,
                stop_loss=price * (1 - self.params["stop_loss_pct"]),
                take_profit=mid,
                position_size=self.params["max_position"],
                leverage=self.params["max_leverage"],
                reasoning="Price touched lower band in low-volatility range.",
            )

        if price >= upper / self.params["touch_threshold"] and rsi_val > self.params[
            "rsi_overbought"
        ]:
            return StrategySignal(
                strategy=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal_type=SignalType.SELL,
                confidence=0.75,
                timestamp=ts,
                price=price,
                stop_loss=price * (1 + self.params["stop_loss_pct"]),
                take_profit=mid,
                position_size=self.params["max_position"],
                leverage=self.params["max_leverage"],
                reasoning="Price touched upper band in low-volatility range.",
            )

        return self._hold("no_signal")

    def _hold(self, reason: str) -> StrategySignal:
        ts = 0
        price = 0.0
        df = self.get_candles()
        if not df.empty:
            ts = int(df.iloc[-1]["timestamp"])
            price = float(df.iloc[-1]["close"])
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
