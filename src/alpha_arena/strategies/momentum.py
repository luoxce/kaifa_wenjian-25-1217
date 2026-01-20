"""Momentum strategy with price, volume, and RSI confirmation."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import atr, rsi, volume_ma
from alpha_arena.strategies.signals import SignalType, StrategySignal

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """Multi-factor momentum strategy for trend/breakout regimes."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "momentum_period": 14,
            "price_momentum_threshold": 0.05,
            "volume_momentum_threshold": 1.3,
            "rsi_period": 14,
            "rsi_momentum_threshold": 5,
            "atr_period": 14,
            "stop_loss_atr": 2.5,
            "take_profit_atr": 5.0,
            "max_position": 0.20,
            "max_leverage": 3,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "momentum",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )

    def generate_signal(self) -> StrategySignal:
        """Generate momentum signals with multi-factor confirmation."""
        try:
            df = self.get_candles()
        except Exception as exc:
            logger.exception("MomentumStrategy failed to load candles: %s", exc)
            return self._hold("data_error")

        required_cols = {"timestamp", "high", "low", "close", "volume"}
        if df.empty or not required_cols.issubset(df.columns):
            return self._hold("not_enough_data")

        momentum_period = int(self.params["momentum_period"])
        rsi_period = int(self.params["rsi_period"])
        atr_period = int(self.params["atr_period"])
        min_len = max(momentum_period + 2, rsi_period + 2, atr_period + 2)
        if len(df) < min_len:
            return self._hold("not_enough_data")

        try:
            df = df.copy()
            df["atr"] = atr(df, atr_period)
            df["rsi"] = rsi(df["close"], rsi_period)
            df["volume_ma"] = volume_ma(df["volume"], momentum_period)

            # Momentum uses percentage change across the lookback window.
            df["price_momentum"] = df["close"].pct_change(periods=momentum_period).fillna(0.0)
            rsi_base = df["rsi"].shift(momentum_period)
            rsi_base = rsi_base.where(rsi_base != 0)
            df["rsi_momentum"] = ((df["rsi"] - rsi_base) / rsi_base * 100).fillna(0.0)

            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = float(last["close"])
            ts = int(last["timestamp"])
            if price <= 0:
                return self._hold("invalid_price")

            price_mom = float(last["price_momentum"]) if pd.notna(last["price_momentum"]) else 0.0
            price_mom_prev = (
                float(prev["price_momentum"]) if pd.notna(prev["price_momentum"]) else 0.0
            )
            rsi_mom = float(last["rsi_momentum"]) if pd.notna(last["rsi_momentum"]) else 0.0
            rsi_mom_prev = (
                float(prev["rsi_momentum"]) if pd.notna(prev["rsi_momentum"]) else 0.0
            )

            volume_ma_val = float(last["volume_ma"]) if pd.notna(last["volume_ma"]) else 0.0
            volume_ratio = (
                float(last["volume"] / volume_ma_val) if volume_ma_val > 0 else 0.0
            )

            price_threshold = float(self.params["price_momentum_threshold"])
            volume_threshold = float(self.params["volume_momentum_threshold"])
            rsi_threshold = float(self.params["rsi_momentum_threshold"])

            # Require alignment plus persistence to avoid choppy market signals.
            long_confirmed = (
                price_mom >= price_threshold
                and volume_ratio >= volume_threshold
                and rsi_mom >= rsi_threshold
                and price_mom_prev > 0
                and rsi_mom_prev > 0
            )
            short_confirmed = (
                price_mom <= -price_threshold
                and volume_ratio >= volume_threshold
                and rsi_mom <= -rsi_threshold
                and price_mom_prev < 0
                and rsi_mom_prev < 0
            )

            atr_val = float(last["atr"]) if pd.notna(last["atr"]) else 0.0

            if long_confirmed:
                stop_loss = price - atr_val * self.params["stop_loss_atr"] if atr_val else None
                take_profit = price + atr_val * self.params["take_profit_atr"] if atr_val else None
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
                        "Momentum aligned up: "
                        f"price {price_mom:.2%}, volume {volume_ratio:.2f}x, "
                        f"rsi {rsi_mom:.2f}%."
                    ),
                )

            if short_confirmed:
                stop_loss = price + atr_val * self.params["stop_loss_atr"] if atr_val else None
                take_profit = price - atr_val * self.params["take_profit_atr"] if atr_val else None
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
                        "Momentum aligned down: "
                        f"price {price_mom:.2%}, volume {volume_ratio:.2f}x, "
                        f"rsi {rsi_mom:.2f}%."
                    ),
                )

            if (
                volume_ratio < volume_threshold
                or abs(price_mom) < price_threshold
                or abs(rsi_mom) < rsi_threshold
            ):
                return self._hold("weak_momentum")

            return self._hold("no_signal")
        except Exception as exc:
            logger.exception("MomentumStrategy failed during signal generation: %s", exc)
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
