"""Train or evaluate a PPO agent for TradingEnv."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import numpy as np

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
except ImportError as exc:  # pragma: no cover - runtime dependency
    PPO = None
    CheckpointCallback = None
    EvalCallback = None
    DummyVecEnv = None
    VecNormalize = None
    _SB3_IMPORT_ERROR = exc
else:
    _SB3_IMPORT_ERROR = None

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.rl.trading_env import TradingEnv


DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "BTC/USDT:USDT",
    "timeframe": "1h",
    "initial_equity": 10000,
    "max_position": 3.0,
    "lookback_window": 100,
    "transaction_fee": 0.0005,
    "total_timesteps": 100000,
    "n_envs": 4,
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "save_dir": "models/rl",
    "checkpoint_freq": 10000,
    "eval_freq": 5000,
    "device": "auto",
    "tensorboard": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train or evaluate PPO agent.")
    parser.add_argument("--mode", choices=("train", "eval"), default="train")
    parser.add_argument("--config", default="", help="Optional JSON config file.")
    parser.add_argument("--model", default="", help="Model path for eval mode.")
    parser.add_argument("--episodes", type=int, default=10, help="Eval episodes.")

    parser.add_argument("--symbol", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--initial-equity", type=float, default=None)
    parser.add_argument("--max-position", type=float, default=None)
    parser.add_argument("--lookback-window", type=int, default=None)
    parser.add_argument("--transaction-fee", type=float, default=None)

    parser.add_argument("--total-timesteps", type=int, default=None)
    parser.add_argument("--n-envs", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--n-epochs", type=int, default=None)
    parser.add_argument("--gamma", type=float, default=None)
    parser.add_argument("--gae-lambda", type=float, default=None)
    parser.add_argument("--clip-range", type=float, default=None)
    parser.add_argument("--ent-coef", type=float, default=None)
    parser.add_argument("--save-dir", default=None)
    parser.add_argument("--checkpoint-freq", type=int, default=None)
    parser.add_argument("--eval-freq", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--device", default=None, help="Torch device: auto/cpu/cuda")
    return parser.parse_args()


def load_config(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def merge_config(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def build_env(config: Dict[str, Any]) -> TradingEnv:
    return TradingEnv(
        symbol=config["symbol"],
        timeframe=config["timeframe"],
        initial_equity=config["initial_equity"],
        max_position=config["max_position"],
        lookback_window=config["lookback_window"],
        transaction_fee=config["transaction_fee"],
    )


def ensure_dirs(root: Path) -> Dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "root": root,
        "checkpoints": root / "checkpoints",
        "best_model": root / "best_model",
        "tensorboard": root / "tensorboard",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _tensorboard_available() -> bool:
    try:
        import tensorboard  # noqa: F401
    except Exception:
        return False
    return True


def _tensorboard_enabled(config: Dict[str, Any]) -> bool:
    value = config.get("tensorboard", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def train(config: Dict[str, Any]) -> None:
    if PPO is None:
        raise ImportError("stable-baselines3 not installed") from _SB3_IMPORT_ERROR

    save_root = Path(config.get("save_dir") or "models/rl")
    paths = ensure_dirs(save_root)
    tensorboard_log = (
        str(paths["tensorboard"])
        if _tensorboard_available() and _tensorboard_enabled(config)
        else None
    )

    env = DummyVecEnv([lambda: build_env(config) for _ in range(config["n_envs"])])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    eval_env = DummyVecEnv([lambda: build_env(config)])
    eval_env = VecNormalize(eval_env, norm_obs=True, norm_reward=False, clip_obs=10.0)

    checkpoint_cb = CheckpointCallback(
        save_freq=int(config.get("checkpoint_freq", 10000)),
        save_path=str(paths["checkpoints"]),
        name_prefix="ppo_trading",
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(paths["best_model"]),
        log_path=str(paths["best_model"]),
        eval_freq=int(config.get("eval_freq", 5000)),
        deterministic=True,
    )

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=config["learning_rate"],
        n_steps=config["n_steps"],
        batch_size=config["batch_size"],
        n_epochs=config["n_epochs"],
        gamma=config["gamma"],
        gae_lambda=config["gae_lambda"],
        clip_range=config["clip_range"],
        ent_coef=config["ent_coef"],
        tensorboard_log=tensorboard_log,
        device=config.get("device", "auto"),
        seed=config.get("seed"),
        verbose=1,
    )

    model.learn(
        total_timesteps=config["total_timesteps"],
        callback=[checkpoint_cb, eval_cb],
    )

    model.save(str(save_root / "ppo_trading_final"))
    env.save(str(save_root / "vec_normalize.pkl"))


def evaluate(config: Dict[str, Any], model_path: str, episodes: int) -> None:
    if PPO is None:
        raise ImportError("stable-baselines3 not installed") from _SB3_IMPORT_ERROR
    if not model_path:
        raise ValueError("Model path required for eval mode.")

    env = DummyVecEnv([lambda: build_env(config)])
    vec_path = Path(config.get("save_dir") or "models/rl") / "vec_normalize.pkl"
    if vec_path.exists() and VecNormalize is not None:
        env = VecNormalize.load(str(vec_path), env)
        env.training = False
        env.norm_reward = False

    model = PPO.load(model_path)

    episode_returns = []
    win_count = 0
    sharpe_scores = []
    drawdowns = []

    for _ in range(episodes):
        obs = env.reset()
        done = False
        equity = config["initial_equity"]
        max_equity = equity
        returns = []
        max_drawdown = 0.0

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, info = env.step(action)
            info0 = info[0] if isinstance(info, list) else info
            equity = info0.get("equity", equity)
            max_equity = max(max_equity, equity)
            max_drawdown = max(max_drawdown, info0.get("drawdown", 0.0))
            returns.append(info0.get("step_return", 0.0))

        total_return = equity / config["initial_equity"] - 1.0
        episode_returns.append(total_return)
        if total_return > 0:
            win_count += 1
        sharpe_scores.append(_compute_sharpe(returns))
        drawdowns.append(max_drawdown)

    avg_return = float(np.mean(episode_returns)) if episode_returns else 0.0
    win_rate = win_count / episodes if episodes > 0 else 0.0
    avg_sharpe = float(np.mean(sharpe_scores)) if sharpe_scores else 0.0
    max_drawdown = float(np.max(drawdowns)) if drawdowns else 0.0

    print("Evaluation Report")
    print(f"Episodes: {episodes}")
    print(f"Average Return: {avg_return:.4f}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Sharpe Ratio: {avg_sharpe:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2%}")


def _compute_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    arr = np.array(returns, dtype=np.float32)
    std = float(np.std(arr))
    if std <= 0:
        return 0.0
    return float(np.mean(arr) / std * np.sqrt(252.0))


def main() -> None:
    args = parse_args()
    file_config = load_config(args.config) if args.config else {}
    cli_config = {
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "initial_equity": args.initial_equity,
        "max_position": args.max_position,
        "lookback_window": args.lookback_window,
        "transaction_fee": args.transaction_fee,
        "total_timesteps": args.total_timesteps,
        "n_envs": args.n_envs,
        "learning_rate": args.learning_rate,
        "n_steps": args.n_steps,
        "batch_size": args.batch_size,
        "n_epochs": args.n_epochs,
        "gamma": args.gamma,
        "gae_lambda": args.gae_lambda,
        "clip_range": args.clip_range,
        "ent_coef": args.ent_coef,
        "save_dir": args.save_dir,
        "checkpoint_freq": args.checkpoint_freq,
        "eval_freq": args.eval_freq,
        "seed": args.seed,
        "device": args.device,
    }
    config = merge_config(DEFAULT_CONFIG, file_config)
    config = merge_config(config, cli_config)

    if args.mode == "train":
        train(config)
    else:
        evaluate(config, args.model, args.episodes)


if __name__ == "__main__":
    main()
