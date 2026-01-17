"""End-to-end pytest suite for RL modules."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pytest

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
except ImportError:  # pragma: no cover - optional dependency
    PPO = None
    CheckpointCallback = None
    DummyVecEnv = None
    VecNormalize = None

from alpha_arena.data.data_service import DataService
from alpha_arena.rl.trading_env import TradingEnv
from alpha_arena.rl.rl_integration import RLDecisionMaker
from alpha_arena.decision.hybrid_system import DecisionMode, HybridDecisionSystem


REPORT_PATH = Path("reports") / "rl_test_report.txt"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


@contextmanager
def report_step(name: str):
    start = time.perf_counter()
    status = "PASS"
    error = ""
    try:
        yield
    except Exception as exc:
        status = "FAIL"
        error = str(exc)
        raise
    finally:
        duration = time.perf_counter() - start
        write_report_line(name, status, duration, error)
        if _env_flag("RL_TEST_VERBOSE"):
            color = "\033[32m" if status == "PASS" else "\033[31m"
            reset = "\033[0m"
            print(f"{color}[{status}] {name} ({duration:.2f}s){reset}")


def write_report_line(name: str, status: str, duration: float, error: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}\t{status}\t{duration:.2f}s\t{error}\n")


@pytest.fixture(scope="session")
def model_artifacts(tmp_path_factory) -> Optional[Dict[str, Path]]:
    if _env_flag("RL_TEST_QUICK"):
        return None
    if PPO is None:
        pytest.skip("stable-baselines3 not installed")

    save_artifacts = _env_flag("RL_TEST_SAVE_ARTIFACTS")
    root = (
        Path("models") / "rl" / "test_artifacts"
        if save_artifacts
        else tmp_path_factory.mktemp("rl_test")
    )
    root.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = root / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    env = DummyVecEnv([lambda: TradingEnv()])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    callback = CheckpointCallback(
        save_freq=500,
        save_path=str(checkpoint_dir),
        name_prefix="ppo_test",
    )
    model = PPO("MlpPolicy", env, n_steps=128, batch_size=64, verbose=0)
    model.learn(total_timesteps=1000, callback=callback)

    model_path = root / "ppo_test_model"
    model.save(str(model_path))
    env.save(str(root / "vec_normalize.pkl"))

    return {
        "model_path": model_path.with_suffix(".zip"),
        "checkpoint_dir": checkpoint_dir,
        "vec_path": root / "vec_normalize.pkl",
    }


def test_data_loading():
    with report_step("data_loading"):
        service = DataService()
        candles = service.get_ohlcv("BTC/USDT:USDT", "1h", limit=2000)
        assert len(candles) >= 2000, "Not enough candles for RL training."


def test_env_initialization():
    with report_step("env_initialization"):
        env = TradingEnv()
        obs, _ = env.reset()
        assert env.observation_space.shape == (50,)
        assert env.action_space.shape == (4,)
        assert obs.shape == (50,)
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == (50,)
        assert isinstance(reward, float)
        assert isinstance(info, dict)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)


def test_model_training(model_artifacts):
    with report_step("model_training"):
        if model_artifacts is None:
            pytest.skip("Quick mode enabled or SB3 missing.")
        model_path = model_artifacts["model_path"]
        checkpoint_dir = model_artifacts["checkpoint_dir"]
        assert model_path.exists(), "Model file not created."
        checkpoints = list(checkpoint_dir.glob("*.zip"))
        assert checkpoints, "Checkpoint files missing."


def test_model_loading(model_artifacts):
    with report_step("model_loading"):
        if model_artifacts is None:
            pytest.skip("Quick mode enabled or SB3 missing.")
        model_path = model_artifacts["model_path"]
        assert model_path.exists()
        model = PPO.load(str(model_path))
        env = DummyVecEnv([lambda: TradingEnv()])
        obs = env.reset()
        action, _ = model.predict(obs, deterministic=True)
        assert action is not None


def test_rl_decision_integration():
    with report_step("rl_decision_integration"):
        decision = {
            "symbol": "BTC/USDT:USDT",
            "timeframe": "1h",
            "regime": "RANGE",
            "allocations": [
                {"strategy_id": "ema_trend", "weight": 0.5, "score": 0.6},
                {"strategy_id": "bollinger_range", "weight": 0.5, "score": 0.4},
            ],
            "indicators": {"RSI": 52.0, "BB_Width": 0.03, "MACD": 0.1, "MACD_Signal": 0.05},
        }
        rl = RLDecisionMaker(model_path="missing.zip", use_rl=False)
        updated = rl.integrate_with_portfolio_decision(decision, confidence_threshold=0.7)
        assert "rl_adjusted" in updated
        assert "allocations" in updated


def test_hybrid_system_modes():
    with report_step("hybrid_system_modes"):
        class DummyPortfolio:
            def decide(self, symbol, timeframe, limit=200):
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "timestamp": 0,
                    "regime": "RANGE",
                    "allocations": [
                        {"strategy_id": "ema_trend", "weight": 0.6, "score": 0.6},
                        {"strategy_id": "bollinger_range", "weight": 0.4, "score": 0.4},
                    ],
                    "indicators": {"RSI": 50.0, "BB_Width": 0.02, "MACD": 0.1, "MACD_Signal": 0.08},
                    "reasoning": "test",
                }

        class DummyRL:
            def get_rl_action(self, _market):
                return 0.5, np.array([0.5, 0.3, 0.2], dtype=np.float32)

        system = HybridDecisionSystem(
            data_service=DataService(),
            llm_decision_maker=None,
            rl_decision_maker=DummyRL(),
            portfolio_decision=DummyPortfolio(),
            mode=DecisionMode.HYBRID,
            symbol="BTC/USDT:USDT",
            timeframe="1h",
        )
        decision = system.make_decision(limit=200)
        assert decision is not None
        report = system.get_performance_report()
        assert "rl_calls" in report


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run RL module tests.")
    parser.add_argument("--quick", action="store_true", help="Skip training-heavy tests.")
    parser.add_argument("--verbose", action="store_true", help="Verbose output.")
    parser.add_argument("--save-artifacts", action="store_true", help="Keep model artifacts.")
    args, extra = parser.parse_known_args()

    if args.quick:
        os.environ["RL_TEST_QUICK"] = "true"
    if args.verbose:
        os.environ["RL_TEST_VERBOSE"] = "true"
    if args.save_artifacts:
        os.environ["RL_TEST_SAVE_ARTIFACTS"] = "true"

    ret = pytest.main([__file__, "-s", "-q", *extra])
    sys.exit(ret)


if __name__ == "__main__":
    main()

