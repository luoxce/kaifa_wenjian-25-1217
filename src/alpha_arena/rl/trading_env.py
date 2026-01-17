"""Gymnasium trading environment for RL training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

import gymnasium as gym
from gymnasium import spaces

from alpha_arena.data.data_service import DataService

try:
    import talib
except ImportError as exc:  # pragma: no cover - handled at runtime
    talib = None
    _TALIB_IMPORT_ERROR = exc
else:
    _TALIB_IMPORT_ERROR = None


@dataclass
class TradingEnvState:
    """Runtime state tracking for reward and observation."""

    equity: float
    max_equity: float
    position: float
    drawdown: float
    sharpe: float
    step_return: float


class TradingEnv(gym.Env):
    """RL trading environment with indicator-driven observations."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        initial_equity: float = 10000.0,
        max_position: float = 3.0,
        lookback_window: int = 100,
        transaction_fee: float = 0.0005,
        data_service: Optional[DataService] = None,
        data_limit: Optional[int] = None,
    ) -> None:
        if talib is None:
            raise ImportError(
                "talib is required for TradingEnv. Install TA-Lib before use."
            ) from _TALIB_IMPORT_ERROR

        super().__init__()

        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_equity = float(initial_equity)
        self.max_position = float(max_position)
        self.lookback_window = int(lookback_window)
        self.transaction_fee = float(transaction_fee)
        self.data_service = data_service or DataService()

        limit = int(data_limit or 5000)
        if limit < self.lookback_window + 2:
            limit = self.lookback_window + 2

        self._candles = self.data_service.get_ohlcv(
            self.symbol, self.timeframe, limit=limit
        )
        if self._candles.empty:
            raise ValueError("No candle data available for TradingEnv.")

        self._candles = self._candles.reset_index(drop=True)
        self._close = self._candles["close"].astype(float).to_numpy()
        self._open = self._candles["open"].astype(float).to_numpy()
        self._high = self._candles["high"].astype(float).to_numpy()
        self._low = self._candles["low"].astype(float).to_numpy()
        self._volume = self._candles["volume"].astype(float).fillna(0.0).to_numpy()
        self._timestamp = self._candles["timestamp"].astype(int).to_numpy()

        self._rsi = talib.RSI(self._close, timeperiod=14)
        self._ema_fast = talib.EMA(self._close, timeperiod=12)
        self._ema_slow = talib.EMA(self._close, timeperiod=26)
        bb_upper, bb_middle, bb_lower = talib.BBANDS(
            self._close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        self._bb_upper = bb_upper
        self._bb_middle = bb_middle
        self._bb_lower = bb_lower
        self._atr = talib.ATR(self._high, self._low, self._close, timeperiod=14)
        vol_sma = talib.SMA(self._volume, timeperiod=20)
        self._vol_ratio = np.where(vol_sma > 0, self._volume / vol_sma, 0.0)

        self._funding = self._load_funding_series()

        self.action_space = spaces.Box(
            low=np.array([-1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32
        )

        self._index = self.lookback_window
        self._returns: list[float] = []
        self._state = TradingEnvState(
            equity=self.initial_equity,
            max_equity=self.initial_equity,
            position=0.0,
            drawdown=0.0,
            sharpe=0.0,
            step_return=0.0,
        )

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self._index = self.lookback_window
        self._returns = []
        self._state = TradingEnvState(
            equity=self.initial_equity,
            max_equity=self.initial_equity,
            position=0.0,
            drawdown=0.0,
            sharpe=0.0,
            step_return=0.0,
        )
        return self._get_observation(), {}

    def step(self, action: np.ndarray):
        action = np.asarray(action, dtype=np.float32)
        if action.shape != (4,):
            raise ValueError(f"Action must be shape (4,), got {action.shape}.")

        target_position = float(np.clip(action[0], -1.0, 1.0))
        weights = np.clip(action[1:], 0.0, 1.0)
        weight_sum = float(weights.sum())
        if weight_sum <= 0:
            weights = np.array([1 / 3, 1 / 3, 1 / 3], dtype=np.float32)
        else:
            weights = (weights / weight_sum).astype(np.float32)

        current_position = self._state.position
        new_position = target_position * self.max_position
        turnover = abs(new_position - current_position)

        if self._index >= len(self._close) - 1:
            return self._get_observation(), 0.0, True, False, {}

        prev_equity = self._state.equity
        price = self._close[self._index]
        next_price = self._close[self._index + 1]
        price_return = (next_price - price) / price if price > 0 else 0.0

        fee_cost = turnover * prev_equity * self.transaction_fee
        pnl = new_position * prev_equity * price_return
        equity = max(prev_equity + pnl - fee_cost, 0.0)

        step_return = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
        self._returns.append(step_return)
        sharpe = self._compute_sharpe(self._returns)

        max_equity = max(self._state.max_equity, equity)
        drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0.0

        concentration_penalty = self._concentration_penalty(weights)
        reward = (
            step_return * 100.0
            + sharpe * 0.1
            - drawdown * 10.0
            - turnover * 0.01
            - concentration_penalty * 0.1
        )

        self._state = TradingEnvState(
            equity=equity,
            max_equity=max_equity,
            position=new_position,
            drawdown=drawdown,
            sharpe=sharpe,
            step_return=step_return,
        )

        self._index += 1
        terminated = self._index >= len(self._close) - 1

        info = {
            "equity": equity,
            "drawdown": drawdown,
            "sharpe": sharpe,
            "turnover": turnover,
            "step_return": step_return,
            "weights": weights.tolist(),
            "position": new_position,
            "timestamp": int(self._timestamp[self._index]),
        }
        return self._get_observation(), float(reward), terminated, False, info

    def _get_observation(self) -> np.ndarray:
        idx = self._index
        start = max(0, idx - self.lookback_window + 1)
        window_prices = self._close[start : idx + 1]
        returns = np.diff(window_prices) / window_prices[:-1] if len(window_prices) > 1 else np.array([])

        price_stats = self._price_stats(returns)
        tech_values = self._indicator_values(idx)
        signal_values = self._strategy_signals(idx)
        account_values = self._account_features()
        regime_one_hot = self._market_regime(idx)
        recent_returns = self._recent_returns(returns, count=20)
        recent_vol_ratio = self._recent_vol_ratio(idx, count=6)

        features = np.concatenate(
            [
                price_stats,
                tech_values,
                signal_values,
                account_values,
                regime_one_hot,
                recent_returns,
                recent_vol_ratio,
            ]
        ).astype(np.float32)

        if features.shape[0] != 50:
            raise ValueError(f"Observation size mismatch: {features.shape[0]} != 50")
        return features

    def _price_stats(self, returns: np.ndarray) -> np.ndarray:
        if returns.size == 0:
            return np.zeros(4, dtype=np.float32)
        mean = float(np.mean(returns))
        std = float(np.std(returns)) if returns.size > 1 else 0.0
        if std <= 0:
            return np.array([mean, std, 0.0, 0.0], dtype=np.float32)
        normalized = (returns - mean) / std
        skew = float(np.mean(normalized**3))
        kurt = float(np.mean(normalized**4) - 3.0)
        return np.array([mean, std, skew, kurt], dtype=np.float32)

    def _indicator_values(self, idx: int) -> np.ndarray:
        rsi = self._safe_value(self._rsi, idx)
        ema_fast = self._safe_value(self._ema_fast, idx)
        ema_slow = self._safe_value(self._ema_slow, idx)
        bb_upper = self._safe_value(self._bb_upper, idx)
        bb_middle = self._safe_value(self._bb_middle, idx)
        bb_lower = self._safe_value(self._bb_lower, idx)
        atr = self._safe_value(self._atr, idx)
        vol_ratio = self._safe_value(self._vol_ratio, idx)
        return np.array(
            [rsi, ema_fast, ema_slow, bb_upper, bb_middle, bb_lower, atr, vol_ratio],
            dtype=np.float32,
        )

    def _strategy_signals(self, idx: int) -> np.ndarray:
        ema_fast = self._safe_value(self._ema_fast, idx)
        ema_slow = self._safe_value(self._ema_slow, idx)
        ema_signal = np.sign(ema_fast - ema_slow)

        close = self._close[idx]
        bb_upper = self._safe_value(self._bb_upper, idx)
        bb_lower = self._safe_value(self._bb_lower, idx)
        if close < bb_lower:
            bollinger_signal = 1.0
        elif close > bb_upper:
            bollinger_signal = -1.0
        else:
            bollinger_signal = 0.0

        funding_rate = self._funding.get(idx, 0.0)
        if funding_rate > 0:
            funding_signal = -1.0
        elif funding_rate < 0:
            funding_signal = 1.0
        else:
            funding_signal = 0.0

        return np.array([ema_signal, bollinger_signal, funding_signal], dtype=np.float32)

    def _account_features(self) -> np.ndarray:
        return np.array(
            [
                self._state.position / max(self.max_position, 1e-6),
                self._state.equity / max(self.initial_equity, 1e-6),
                self._state.drawdown,
                self._state.sharpe,
            ],
            dtype=np.float32,
        )

    def _market_regime(self, idx: int) -> np.ndarray:
        ema_fast = self._safe_value(self._ema_fast, idx)
        ema_slow = self._safe_value(self._ema_slow, idx)
        atr = self._safe_value(self._atr, idx)
        price = self._close[idx]
        volatility = atr / price if price > 0 else 0.0
        trend_strength = abs(ema_fast - ema_slow) / price if price > 0 else 0.0
        bb_width = 0.0
        bb_middle = self._safe_value(self._bb_middle, idx)
        if bb_middle > 0:
            bb_width = (self._safe_value(self._bb_upper, idx) - self._safe_value(self._bb_lower, idx)) / bb_middle

        if trend_strength > 0.002 and ema_fast > ema_slow:
            regime = 0  # trend_up
        elif trend_strength > 0.002 and ema_fast < ema_slow:
            regime = 1  # trend_down
        elif volatility > 0.02:
            regime = 3  # high_vol
        elif volatility < 0.005:
            regime = 4  # low_vol
        else:
            regime = 2  # range

        one_hot = np.zeros(5, dtype=np.float32)
        one_hot[regime] = 1.0
        return one_hot

    def _recent_returns(self, returns: np.ndarray, count: int) -> np.ndarray:
        if returns.size == 0:
            return np.zeros(count, dtype=np.float32)
        pad = max(0, count - returns.size)
        recent = returns[-count:] if returns.size >= count else returns
        if pad:
            recent = np.concatenate([np.zeros(pad), recent])
        return recent.astype(np.float32)

    def _recent_vol_ratio(self, idx: int, count: int) -> np.ndarray:
        start = max(0, idx - count + 1)
        values = self._vol_ratio[start : idx + 1]
        pad = max(0, count - len(values))
        if pad:
            values = np.concatenate([np.zeros(pad), values])
        return values.astype(np.float32)

    def _safe_value(self, arr: np.ndarray, idx: int) -> float:
        if idx < 0 or idx >= len(arr):
            return 0.0
        value = arr[idx]
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return 0.0
        return float(value)

    def _compute_sharpe(self, returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns, dtype=np.float32)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        if std <= 0:
            return 0.0
        return mean / std * np.sqrt(252.0)

    def _concentration_penalty(self, weights: np.ndarray) -> float:
        max_weight = float(np.max(weights)) if weights.size else 0.0
        return max(0.0, max_weight - 1 / 3)

    def _load_funding_series(self) -> Dict[int, float]:
        series: Dict[int, float] = {}
        try:
            funding = self.data_service.get_funding_history(self.symbol, limit=5000)
        except Exception:
            return series
        if funding.empty:
            return series
        funding = funding.sort_values("timestamp").reset_index(drop=True)
        fund_idx = 0
        current_rate = 0.0
        for idx, ts in enumerate(self._timestamp):
            while fund_idx < len(funding) and funding.loc[fund_idx, "timestamp"] <= ts:
                current_rate = float(funding.loc[fund_idx, "funding_rate"] or 0.0)
                fund_idx += 1
            series[idx] = current_rate
        return series

