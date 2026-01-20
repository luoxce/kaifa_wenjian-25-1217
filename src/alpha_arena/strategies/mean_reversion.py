"""Mean reversion strategy based on Z-score and RSI extremes."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import adx, rsi
from alpha_arena.strategies.signals import SignalType, StrategySignal

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy with Z-score and RSI confirmation."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "ma_period": 20,
            "std_period": 20,
            "entry_std": 2.0,
            "exit_std": 0.5,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "stop_loss_pct": 0.03,
            "max_position": 0.25,
            "max_leverage": 2,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "mean_reversion",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )

    def generate_signal(self) -> StrategySignal:
        """Generate mean reversion entry/exit signals."""
        try:
            df = self.get_candles()
        except Exception as exc:
            logger.exception("MeanReversionStrategy failed to load candles: %s", exc)
            return self._hold("data_error")

        required_cols = {"timestamp", "high", "low", "close"}
        if df.empty or not required_cols.issubset(df.columns):
            return self._hold("not_enough_data")

        ma_period = int(self.params["ma_period"])
        std_period = int(self.params["std_period"])
        rsi_period = int(self.params["rsi_period"])
        min_len = max(ma_period + 2, std_period + 2, rsi_period + 2)
        if len(df) < min_len:
            return self._hold("not_enough_data")

        try:
            df = df.copy()
            df["ma"] = df["close"].rolling(window=ma_period).mean()
            df["std"] = df["close"].rolling(window=std_period).std()
            df["rsi"] = rsi(df["close"], rsi_period)
            df["adx"] = adx(df, rsi_period)

            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = float(last["close"])
            ts = int(last["timestamp"])
            if price <= 0:
                return self._hold("invalid_price")

            mean = float(last["ma"]) if pd.notna(last["ma"]) else 0.0
            std = float(last["std"]) if pd.notna(last["std"]) else 0.0
            if mean <= 0 or std <= 0:
                return self._hold("invalid_stats")

            z_score = (price - mean) / std
            prev_mean = float(prev["ma"]) if pd.notna(prev["ma"]) else mean
            prev_std = float(prev["std"]) if pd.notna(prev["std"]) else std
            prev_z = (float(prev["close"]) - prev_mean) / prev_std if prev_std else 0.0

            rsi_val = float(last["rsi"]) if pd.notna(last["rsi"]) else 0.0
            adx_val = float(last["adx"]) if pd.notna(last["adx"]) else 0.0

            entry_std = float(self.params["entry_std"])
            exit_std = float(self.params["exit_std"])

            # Trend filter: skip mean reversion when trend strength is high.
            if adx_val > 25:
                if prev_z >= exit_std and z_score < exit_std:
                    return self._close_short(price, ts, "mean_reversion_exit_short")
                if prev_z <= -exit_std and z_score > -exit_std:
                    return self._close_long(price, ts, "mean_reversion_exit_long")
                return self._hold("trend_filter")

            if rsi_val < float(self.params["rsi_oversold"]) and z_score <= -entry_std:
                stop_loss = price * (1 - float(self.params["stop_loss_pct"]))
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.BUY,
                    confidence=0.78,
                    timestamp=ts,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=mean,
                    position_size=self.params["max_position"],
                    leverage=self.params["max_leverage"],
                    reasoning=f"Z-score {z_score:.2f} and RSI {rsi_val:.1f} oversold.",
                )

            if rsi_val > float(self.params["rsi_overbought"]) and z_score >= entry_std:
                stop_loss = price * (1 + float(self.params["stop_loss_pct"]))
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.SELL,
                    confidence=0.78,
                    timestamp=ts,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=mean,
                    position_size=self.params["max_position"],
                    leverage=self.params["max_leverage"],
                    reasoning=f"Z-score {z_score:.2f} and RSI {rsi_val:.1f} overbought.",
                )

            if prev_z >= exit_std and z_score < exit_std:
                return self._close_short(price, ts, "mean_reversion_exit_short")

            if prev_z <= -exit_std and z_score > -exit_std:
                return self._close_long(price, ts, "mean_reversion_exit_long")

            return self._hold("no_signal")
        except Exception as exc:
            logger.exception("MeanReversionStrategy failed during signal generation: %s", exc)
            return self._hold("error")

    def _close_long(self, price: float, ts: int, reason: str) -> StrategySignal:
        return StrategySignal(
            strategy=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_type=SignalType.CLOSE_LONG,
            confidence=0.6,
            timestamp=ts,
            price=price,
            stop_loss=None,
            take_profit=None,
            position_size=None,
            leverage=None,
            reasoning=reason,
        )

    def _close_short(self, price: float, ts: int, reason: str) -> StrategySignal:
        return StrategySignal(
            strategy=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_type=SignalType.CLOSE_SHORT,
            confidence=0.6,
            timestamp=ts,
            price=price,
            stop_loss=None,
            take_profit=None,
            position_size=None,
            leverage=None,
            reasoning=reason,
        )

    def _hold(self, reason: str) -> StrategySignal:
        ts = 0
        price = 0.0
        try:
            df = self.get_candles()
        except Exception:
            df = pd.DataFrame()
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
