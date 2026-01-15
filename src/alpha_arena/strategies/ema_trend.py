"""EMA trend-following strategy."""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import atr, ema, macd, rsi, volume_ma
from alpha_arena.strategies.signals import SignalType, StrategySignal


class EMATrendStrategy(BaseStrategy):
    """EMA trend strategy based on the BTC strategy library."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "ema_fast": 9,
            "ema_medium": 21,
            "ema_slow": 55,
            "atr_period": 14,
            "stop_loss_atr": 2.0,
            "take_profit_atr": 4.0,
            "max_position": 0.20,
            "max_leverage": 3,
            "rsi_min": 50,
            "rsi_max": 70,
            "rsi_short_min": 30,
            "rsi_short_max": 50,
            "volume_threshold": 1.2,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "ema_trend",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )

    def generate_signal(self) -> StrategySignal:
        df = self.get_candles()
        if df.empty or len(df) < self.params["ema_slow"] + 5:
            return self._hold("not_enough_data")

        df = df.copy()
        df["ema_fast"] = ema(df["close"], self.params["ema_fast"])
        df["ema_medium"] = ema(df["close"], self.params["ema_medium"])
        df["ema_slow"] = ema(df["close"], self.params["ema_slow"])
        df["atr"] = atr(df, self.params["atr_period"])
        df["rsi"] = rsi(df["close"], 14)
        df["volume_ma"] = volume_ma(df["volume"], 20)
        macd_df = macd(df["close"])
        df["macd"] = macd_df["macd"]
        df["macd_signal"] = macd_df["signal"]

        last = df.iloc[-1]
        price = float(last["close"])
        ts = int(last["timestamp"])

        is_uptrend = (
            last["ema_fast"] > last["ema_medium"] > last["ema_slow"]
            and price > last["ema_fast"]
        )
        is_downtrend = (
            last["ema_fast"] < last["ema_medium"] < last["ema_slow"]
            and price < last["ema_fast"]
        )

        volume_ok = last["volume"] > last["volume_ma"] * self.params["volume_threshold"]
        macd_bullish = last["macd"] > last["macd_signal"] and last["macd"] > 0
        macd_bearish = last["macd"] < last["macd_signal"] and last["macd"] < 0
        rsi_val = float(last["rsi"])

        atr_val = float(last["atr"]) if pd.notna(last["atr"]) else 0.0
        stop_loss = price - atr_val * self.params["stop_loss_atr"]
        take_profit = price + atr_val * self.params["take_profit_atr"]

        if is_uptrend and macd_bullish and volume_ok and (
            self.params["rsi_min"] < rsi_val < self.params["rsi_max"]
        ):
            return StrategySignal(
                strategy=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal_type=SignalType.BUY,
                confidence=0.85,
                timestamp=ts,
                price=price,
                stop_loss=stop_loss if atr_val else None,
                take_profit=take_profit if atr_val else None,
                position_size=self.params["max_position"],
                leverage=self.params["max_leverage"],
                reasoning="EMA trend up with MACD confirmation and volume surge.",
            )

        if is_downtrend and macd_bearish and volume_ok and (
            self.params["rsi_short_min"] < rsi_val < self.params["rsi_short_max"]
        ):
            return StrategySignal(
                strategy=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                signal_type=SignalType.SELL,
                confidence=0.85,
                timestamp=ts,
                price=price,
                stop_loss=price + atr_val * self.params["stop_loss_atr"]
                if atr_val
                else None,
                take_profit=price - atr_val * self.params["take_profit_atr"]
                if atr_val
                else None,
                position_size=self.params["max_position"],
                leverage=self.params["max_leverage"],
                reasoning="EMA trend down with MACD confirmation and volume surge.",
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
