"""Grid trading strategy centered on Bollinger mid-band."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

from alpha_arena.strategies.base import BaseStrategy
from alpha_arena.strategies.indicators import bollinger_bands
from alpha_arena.strategies.signals import SignalType, StrategySignal

logger = logging.getLogger(__name__)


class GridTradingStrategy(BaseStrategy):
    """Equal-spaced grid trading strategy for range-bound regimes."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        data_service,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        default_params = {
            "grid_count": 5,
            "grid_range": 0.04,
            "bb_period": 20,
            "bb_std": 2.0,
            "position_per_grid": 0.05,
            "max_position": 0.30,
            "max_leverage": 2,
        }
        if params:
            default_params.update(params)
        super().__init__(
            "grid_trading",
            symbol,
            timeframe,
            data_service,
            params=default_params,
            data_limit=data_limit,
        )
        # Track which grid levels currently have an open position.
        self._grid_positions: dict[int, bool] = {}

    def generate_signal(self) -> StrategySignal:
        """Generate grid trading signals based on price crossing grid lines."""
        try:
            df = self.get_candles()
        except Exception as exc:
            logger.exception("GridTradingStrategy failed to load candles: %s", exc)
            return self._hold("data_error")

        required_cols = {"timestamp", "close"}
        if df.empty or not required_cols.issubset(df.columns):
            return self._hold("not_enough_data")

        bb_period = int(self.params["bb_period"])
        min_len = bb_period + 2
        if len(df) < min_len:
            return self._hold("not_enough_data")

        try:
            df = df.copy()
            bands = bollinger_bands(df["close"], bb_period, float(self.params["bb_std"]))
            df = df.join(bands)

            last = df.iloc[-1]
            price = float(last["close"])
            ts = int(last["timestamp"])
            prev_price = float(df.iloc[-2]["close"])

            mid = float(last["mid"]) if pd.notna(last["mid"]) else 0.0
            bandwidth = float(last["bandwidth"]) if pd.notna(last["bandwidth"]) else 0.0
            if mid <= 0:
                return self._hold("invalid_mid")

            # Grid range uses Bollinger bandwidth when available, with param fallback.
            base_range = float(self.params["grid_range"])
            grid_range = max(base_range, bandwidth * 2.0) if bandwidth > 0 else base_range
            if grid_range <= 0:
                return self._hold("invalid_grid_range")

            grid_count = int(self.params["grid_count"])
            if grid_count < 2:
                return self._hold("invalid_grid_count")

            half_range = grid_range / 2.0
            lower = mid * (1.0 - half_range)
            upper = mid * (1.0 + half_range)
            if lower <= 0 or upper <= 0 or lower >= upper:
                return self._hold("invalid_bounds")

            step = (upper - lower) / (grid_count - 1)
            grid_levels = [lower + step * idx for idx in range(grid_count)]

            self._ensure_grid_positions(grid_count)

            buy_candidates: list[tuple[int, float]] = []
            sell_candidates: list[tuple[int, float]] = []
            for idx, level in enumerate(grid_levels):
                if prev_price > level and price <= level and not self._grid_positions.get(
                    idx, False
                ):
                    buy_candidates.append((idx, level))
                if prev_price < level and price >= level and self._grid_positions.get(
                    idx, False
                ):
                    sell_candidates.append((idx, level))

            if buy_candidates:
                # Pick the closest crossed level to current price for a single signal.
                idx, level = min(buy_candidates, key=lambda item: item[1])
                position_size = self._position_size_for_new_grid()
                if position_size <= 0:
                    return self._hold("max_position_reached")
                self._grid_positions[idx] = True
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.BUY,
                    confidence=0.7,
                    timestamp=ts,
                    price=price,
                    stop_loss=None,
                    take_profit=None,
                    position_size=position_size,
                    leverage=self.params["max_leverage"],
                    reasoning=f"Price crossed below grid level {level:.2f}.",
                )

            if sell_candidates:
                # Pick the closest crossed level to current price for a single signal.
                idx, level = max(sell_candidates, key=lambda item: item[1])
                self._grid_positions[idx] = False
                return StrategySignal(
                    strategy=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    signal_type=SignalType.SELL,
                    confidence=0.7,
                    timestamp=ts,
                    price=price,
                    stop_loss=None,
                    take_profit=None,
                    position_size=float(self.params["position_per_grid"]),
                    leverage=self.params["max_leverage"],
                    reasoning=f"Price crossed above grid level {level:.2f}.",
                )

            return self._hold("no_signal")
        except Exception as exc:
            logger.exception("GridTradingStrategy failed during signal generation: %s", exc)
            return self._hold("error")

    def _ensure_grid_positions(self, grid_count: int) -> None:
        if not self._grid_positions or len(self._grid_positions) != grid_count:
            self._grid_positions = {idx: False for idx in range(grid_count)}
            return
        for idx in range(grid_count):
            self._grid_positions.setdefault(idx, False)
        for idx in list(self._grid_positions.keys()):
            if idx >= grid_count:
                del self._grid_positions[idx]

    def _position_size_for_new_grid(self) -> float:
        position_per_grid = float(self.params["position_per_grid"])
        max_position = float(self.params["max_position"])
        open_count = sum(1 for opened in self._grid_positions.values() if opened)
        current_exposure = open_count * position_per_grid
        remaining = max_position - current_exposure
        if remaining <= 0:
            return 0.0
        return min(position_per_grid, remaining)

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
