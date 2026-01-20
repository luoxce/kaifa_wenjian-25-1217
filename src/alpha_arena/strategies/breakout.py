"""Breakout strategy with volume confirmation and ATR risk controls."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import atr, volume_ma
from alpha_arena.strategies.signals import SignalType, StrategySignal

logger = logging.getLogger(__name__)


class BreakoutStrategy(BaseStrategy):
    """Key level breakout strategy with volume confirmation."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "lookback_period": 20,
            "breakout_threshold": 1.002,
            "volume_threshold": 1.5,
            "atr_period": 14,
            "stop_loss_atr": 2.0,
            "take_profit_atr": 4.0,
            "max_position": 0.25,
            "max_leverage": 3,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "breakout",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )

    def generate_signal(self) -> StrategySignal:
        """Generate breakout signals with volume + ATR guards."""
        try:
            df = self.get_candles()
        except Exception as exc:
            logger.exception("BreakoutStrategy failed to load candles: %s", exc)
            return self._hold("data_error")

        try:
            required_cols = {"timestamp", "high", "low", "close", "volume"}
            if df.empty or not required_cols.issubset(df.columns):
                return self._hold("not_enough_data")

            lookback = int(self.params["lookback_period"])
            atr_period = int(self.params["atr_period"])
            volume_period = lookback
            min_len = max(lookback + 1, atr_period + 1, volume_period + 1)
            if len(df) < min_len:
                return self._hold("not_enough_data")

            df = df.copy()
            # Indicators stay inside the strategy (reuse shared indicator helpers).
            df["atr"] = atr(df, atr_period)
            df["volume_ma"] = volume_ma(df["volume"], volume_period)

            # Use the previous N candles to avoid lookahead bias in key levels.
            history = df.iloc[-(lookback + 1) : -1]
            if history.empty:
                return self._hold("not_enough_history")

            last = df.iloc[-1]
            price = float(last["close"])
            ts = int(last["timestamp"])
            if price <= 0:
                return self._hold("invalid_price")

            resistance = float(history["high"].max())
            support = float(history["low"].min())
            if not pd.notna(resistance) or not pd.notna(support):
                return self._hold("invalid_levels")

            # Add a small buffer to reduce false breakouts.
            breakout_threshold = float(self.params["breakout_threshold"])
            long_breakout = price >= resistance * breakout_threshold
            short_breakout = price <= support / breakout_threshold

            # Confirm breakouts with volume expansion versus its rolling mean.
            volume_ma_val = (
                float(last["volume_ma"]) if pd.notna(last["volume_ma"]) else 0.0
            )
            volume_ratio = (
                float(last["volume"] / volume_ma_val) if volume_ma_val > 0 else 0.0
            )
            volume_ok = volume_ratio >= float(self.params["volume_threshold"])

            # ATR-based risk controls scale with recent volatility.
            atr_val = float(last["atr"]) if pd.notna(last["atr"]) else 0.0
            if long_breakout and volume_ok:
                stop_loss = (
                    price - atr_val * self.params["stop_loss_atr"] if atr_val else None
                )
                take_profit = (
                    price + atr_val * self.params["take_profit_atr"] if atr_val else None
                )
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.BUY,
                    confidence=0.8,
                    timestamp=ts,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=self.params["max_position"],
                    leverage=self.params["max_leverage"],
                    reasoning=(
                        f"Breakout above resistance {resistance:.2f} with volume "
                        f"{volume_ratio:.2f}x."
                    ),
                )

            if short_breakout and volume_ok:
                stop_loss = (
                    price + atr_val * self.params["stop_loss_atr"] if atr_val else None
                )
                take_profit = (
                    price - atr_val * self.params["take_profit_atr"] if atr_val else None
                )
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.SELL,
                    confidence=0.8,
                    timestamp=ts,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=self.params["max_position"],
                    leverage=self.params["max_leverage"],
                    reasoning=(
                        f"Breakdown below support {support:.2f} with volume "
                        f"{volume_ratio:.2f}x."
                    ),
                )

            if long_breakout or short_breakout:
                return self._hold("breakout_without_volume")

            return self._hold("no_signal")
        except Exception as exc:
            logger.exception("BreakoutStrategy failed during signal generation: %s", exc)
            return self._hold("error")

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
