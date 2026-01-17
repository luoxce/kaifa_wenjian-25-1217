"""RL decision integration helpers for live trading."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import numpy as np

from alpha_arena.data.data_service import DataService

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
except ImportError:  # pragma: no cover - optional dependency
    PPO = None
    DummyVecEnv = None
    VecNormalize = None

from alpha_arena.rl.trading_env import TradingEnv

logger = logging.getLogger(__name__)


@dataclass
class RLActionSuggestion:
    target_position: float
    strategy_weights: np.ndarray
    raw_action: np.ndarray


class RLDecisionMaker:
    """Load PPO model and produce RL-enhanced trading actions."""

    def __init__(
        self,
        model_path: str,
        data_service: Optional[DataService] = None,
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        lookback_window: int = 100,
        use_rl: bool = True,
    ) -> None:
        self.model_path = model_path
        self.data_service = data_service or DataService()
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_window = lookback_window
        self.use_rl = use_rl

        self.model = None
        self.vec_normalize = None
        self.model_loaded = False
        self.last_prediction_time: Optional[str] = None
        self._position = 0.0
        self._equity = 0.0

        if self.use_rl:
            self._load_model()

    def _load_model(self) -> None:
        if PPO is None:
            logger.warning("stable-baselines3 not installed; RL disabled.")
            return
        if not os.path.exists(self.model_path):
            logger.warning("RL model not found: %s", self.model_path)
            return
        try:
            self.model = PPO.load(self.model_path)
            self.model_loaded = True
        except Exception as exc:  # pragma: no cover - runtime dependency
            logger.exception("Failed to load RL model: %s", exc)
            self.model_loaded = False
            return

        vec_path = self._resolve_vec_normalize_path()
        if vec_path and os.path.exists(vec_path) and VecNormalize is not None:
            try:
                dummy_env = DummyVecEnv(
                    [
                        lambda: TradingEnv(
                            symbol=self.symbol,
                            timeframe=self.timeframe,
                            lookback_window=self.lookback_window,
                            data_service=self.data_service,
                        )
                    ]
                )
                self.vec_normalize = VecNormalize.load(vec_path, dummy_env)
                self.vec_normalize.training = False
                self.vec_normalize.norm_reward = False
            except Exception as exc:  # pragma: no cover - runtime dependency
                logger.warning("VecNormalize load failed: %s", exc)
                self.vec_normalize = None

    def _resolve_vec_normalize_path(self) -> Optional[str]:
        base_dir = os.path.dirname(self.model_path)
        candidate = os.path.join(base_dir, "..", "vec_normalize.pkl")
        return os.path.abspath(candidate)

    def get_rl_action(self, market_data: Dict[str, float]) -> Tuple[float, np.ndarray]:
        """Return RL target position and normalized strategy weights."""
        if not self.use_rl or not self.model_loaded or self.model is None:
            return 0.0, np.array([0.33, 0.33, 0.34], dtype=np.float32)

        observation = self._construct_observation(market_data)
        obs_input = observation.reshape(1, -1)
        if self.vec_normalize is not None:
            obs_input = self.vec_normalize.normalize_obs(obs_input)

        action, _state = self.model.predict(obs_input, deterministic=True)
        action = np.asarray(action).reshape(-1)
        if action.shape[0] != 4:
            logger.warning("RL action shape mismatch: %s", action.shape)
            return 0.0, np.array([0.33, 0.33, 0.34], dtype=np.float32)

        target_position = float(np.clip(action[0], -1.0, 1.0))
        weights = np.clip(action[1:], 0.0, 1.0)
        total = float(weights.sum())
        if total <= 0:
            weights = np.array([0.33, 0.33, 0.34], dtype=np.float32)
        else:
            weights = (weights / total).astype(np.float32)

        self.last_prediction_time = datetime.now(timezone.utc).isoformat()
        return target_position, weights

    def integrate_with_portfolio_decision(
        self, portfolio_decision: Dict, confidence_threshold: float = 0.7, alpha: float = 0.5
    ) -> Dict:
        """Blend RL suggestion into an existing portfolio decision."""
        if not portfolio_decision:
            return portfolio_decision
        confidence = self._estimate_confidence(portfolio_decision)
        if confidence >= confidence_threshold:
            portfolio_decision["rl_adjusted"] = False
            return portfolio_decision

        market_data = self._build_market_payload(portfolio_decision)
        target_position, weights = self.get_rl_action(market_data)
        original_signal = self._extract_original_signal(portfolio_decision)
        final_signal = alpha * target_position + (1.0 - alpha) * original_signal

        updated = dict(portfolio_decision)
        updated["rl_adjusted"] = True
        updated["rl_contribution"] = alpha
        updated["rl_suggestion"] = {
            "target_position": target_position,
            "strategy_weights": weights.tolist(),
            "original_signal": original_signal,
            "final_signal": final_signal,
        }
        updated["target_position"] = final_signal

        updated["allocations"] = self._apply_weights_to_allocations(
            portfolio_decision.get("allocations", []),
            weights,
            final_signal,
        )
        return updated

    def update_state(self, position: float, equity: float) -> None:
        self._position = float(position)
        self._equity = float(equity)

    def _construct_observation(self, market_data: Dict[str, float]) -> np.ndarray:
        """Construct a 50-dim observation vector aligned with TradingEnv."""
        candles = self.data_service.get_ohlcv(
            self.symbol, self.timeframe, limit=self.lookback_window
        )
        if candles.empty:
            return np.zeros(50, dtype=np.float32)

        candles = candles.reset_index(drop=True)
        close = candles["close"].astype(float).to_numpy()
        high = candles["high"].astype(float).to_numpy()
        low = candles["low"].astype(float).to_numpy()
        volume = candles["volume"].astype(float).fillna(0.0).to_numpy()
        returns = np.diff(close) / close[:-1] if len(close) > 1 else np.array([])

        price_stats = self._price_stats(returns)
        indicators = self._compute_indicators(close, high, low, volume)
        signals = np.array(
            [
                float(market_data.get("ema_signal", 0.0)),
                float(market_data.get("bollinger_signal", 0.0)),
                float(market_data.get("funding_signal", 0.0)),
            ],
            dtype=np.float32,
        )
        account = np.array(
            [
                float(self._position),
                float(self._equity if self._equity > 0 else 1.0),
                float(market_data.get("drawdown", 0.0)),
                float(market_data.get("sharpe", 0.0)),
            ],
            dtype=np.float32,
        )
        regime = self._map_regime(market_data.get("regime", "range"))
        recent_returns = self._recent_series(returns, count=20)
        vol_ratio = self._volume_ratio(volume)
        recent_vol = self._recent_series(vol_ratio, count=6)

        obs = np.concatenate(
            [
                price_stats,
                indicators,
                signals,
                account,
                regime,
                recent_returns,
                recent_vol,
            ]
        ).astype(np.float32)
        if obs.shape[0] != 50:
            return np.zeros(50, dtype=np.float32)
        return obs

    def _compute_indicators(
        self, close: np.ndarray, high: np.ndarray, low: np.ndarray, volume: np.ndarray
    ) -> np.ndarray:
        import talib

        rsi = talib.RSI(close, timeperiod=14)
        ema_fast = talib.EMA(close, timeperiod=12)
        ema_slow = talib.EMA(close, timeperiod=26)
        bb_upper, bb_middle, bb_lower = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        atr = talib.ATR(high, low, close, timeperiod=14)
        vol_sma = talib.SMA(volume, timeperiod=20)
        vol_ratio = np.where(vol_sma > 0, volume / vol_sma, 0.0)

        idx = len(close) - 1
        return np.array(
            [
                self._safe_value(rsi, idx),
                self._safe_value(ema_fast, idx),
                self._safe_value(ema_slow, idx),
                self._safe_value(bb_upper, idx),
                self._safe_value(bb_middle, idx),
                self._safe_value(bb_lower, idx),
                self._safe_value(atr, idx),
                self._safe_value(vol_ratio, idx),
            ],
            dtype=np.float32,
        )

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

    def _recent_series(self, values: np.ndarray, count: int) -> np.ndarray:
        if values.size == 0:
            return np.zeros(count, dtype=np.float32)
        pad = max(0, count - values.size)
        recent = values[-count:] if values.size >= count else values
        if pad:
            recent = np.concatenate([np.zeros(pad), recent])
        return recent.astype(np.float32)

    def _volume_ratio(self, volume: np.ndarray) -> np.ndarray:
        if volume.size == 0:
            return np.array([], dtype=np.float32)
        window = min(20, volume.size)
        mean = np.mean(volume[-window:]) if window > 0 else 0.0
        if mean <= 0:
            return np.zeros_like(volume, dtype=np.float32)
        return (volume / mean).astype(np.float32)

    def _safe_value(self, arr: np.ndarray, idx: int) -> float:
        if idx < 0 or idx >= len(arr):
            return 0.0
        value = arr[idx]
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return 0.0
        return float(value)

    def _map_regime(self, regime: str) -> np.ndarray:
        key = (regime or "").lower()
        mapping = {"trend_up": 0, "trend_down": 1, "range": 2, "high_vol": 3, "low_vol": 4}
        idx = mapping.get(key, 2)
        one_hot = np.zeros(5, dtype=np.float32)
        one_hot[idx] = 1.0
        return one_hot

    def _build_market_payload(self, portfolio_decision: Dict) -> Dict[str, float]:
        indicators = portfolio_decision.get("indicators", {}) or {}
        rsi = float(indicators.get("RSI") or 0.0)
        bb_width = float(indicators.get("BB_Width") or 0.0)
        macd = float(indicators.get("MACD") or 0.0)
        macd_signal = float(indicators.get("MACD_Signal") or 0.0)
        ema_signal = 1.0 if macd > macd_signal else -1.0 if macd < macd_signal else 0.0
        return {
            "rsi": rsi,
            "bb_position": 0.0,
            "bb_width": bb_width,
            "funding_rate": 0.0,
            "ema_signal": ema_signal,
            "bollinger_signal": 0.0,
            "funding_signal": 0.0,
            "regime": portfolio_decision.get("regime", "range"),
        }

    def _estimate_confidence(self, portfolio_decision: Dict) -> float:
        confidence = portfolio_decision.get("confidence")
        if confidence is not None:
            try:
                return float(confidence)
            except (TypeError, ValueError):
                return 0.0

        allocations = portfolio_decision.get("allocations", []) or []
        if not allocations:
            return 0.0
        scores = []
        for item in allocations:
            score = item.get("score")
            if score is None:
                continue
            try:
                scores.append(float(score))
            except (TypeError, ValueError):
                continue
        if not scores:
            return 0.5
        avg_score = sum(scores) / len(scores)
        return max(0.0, min(avg_score, 1.0))

    def _extract_original_signal(self, portfolio_decision: Dict) -> float:
        value = portfolio_decision.get("target_position")
        if value is None:
            allocations = portfolio_decision.get("allocations", []) or []
            weight_sum = sum(float(item.get("weight", 0.0)) for item in allocations)
            return max(0.0, min(weight_sum, 1.0))
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _apply_weights_to_allocations(
        self, allocations: list, weights: np.ndarray, final_signal: float
    ) -> list:
        if final_signal <= 0:
            return []

        weight_map = {
            "ema_trend": float(weights[0]),
            "bollinger_range": float(weights[1]),
            "funding_rate_arbitrage": float(weights[2]),
        }
        updated = []
        for item in allocations:
            strategy_id = item.get("strategy_id")
            if strategy_id in weight_map:
                entry = dict(item)
                entry["weight"] = weight_map[strategy_id]
                updated.append(entry)
        if not updated:
            for key, value in weight_map.items():
                updated.append({"strategy_id": key, "weight": value, "score": value})
        return updated

    def to_status_payload(self) -> Dict[str, object]:
        return {
            "enabled": bool(self.use_rl),
            "model_path": self.model_path,
            "model_loaded": bool(self.model_loaded),
            "last_prediction_time": self.last_prediction_time,
        }

    def to_stats_payload(self) -> Dict[str, object]:
        return {
            "enabled": bool(self.use_rl),
            "position": self._position,
            "equity": self._equity,
        }
