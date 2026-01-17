# Reinforcement Learning Module Guide

## 1. Quick Start

WARNING: RL depends on stable-baselines3, gymnasium, and TA-Lib. Install them first.

Steps:
1) Install dependencies.
2) Ensure you have enough market data.
3) Run the first training session.
4) Enable RL in `.env`.

```bash
pip install stable-baselines3 gymnasium numpy pandas ta-lib
python scripts/train_rl.py --mode train --config configs/rl_config_fast.json
```

SUCCESS: After training, you should see files under `models/rl/`.

## 2. Configuration

### 2.1 .env settings
- `RL_ENABLED`: enable RL integration in trading loop.
- `RL_MODEL_PATH`: path to the PPO model.
- `RL_CONFIDENCE_THRESHOLD`: threshold for RL to intervene.
- `DECISION_MODE`: `hybrid`, `rl_only`, `llm_only`, `safe_mode`.

### 2.2 Training config
Use `configs/rl_config.json` or `configs/rl_config_fast.json` as templates.

Recommended:
- `total_timesteps`: 500000 for full training.
- `n_envs`: 4 or higher if CPU allows.
- `learning_rate`: 3e-4.

Optional:
- `device`: `auto` (default), `cpu`, or `cuda`.
- `tensorboard`: `true`/`false` to enable or disable TensorBoard logging.

## 3. Training Workflow

Checklist:
- At least 2000 candles available for the target timeframe.
- Database and DataService working.
- TA-Lib installed correctly.

Train example:
```bash
python scripts/train_rl.py --mode train --config configs/rl_config.json
```

GPU training (optional):
```bash
# requires CUDA-enabled PyTorch; use --device cpu if CUDA is not available
python scripts/train_rl.py --mode train --config configs/rl_config.json --device cuda
```

TensorBoard:
```bash
tensorboard --logdir models/rl/tensorboard
```

Common issues:
- If TA-Lib import fails, reinstall OS-specific binaries.
- If training is slow, reduce `n_steps` or `n_envs`.
- If you see "tensorboard is not installed", either install `tensorboard` or set `tensorboard=false`.

## 4. Evaluation and Deployment

Evaluate:
```bash
python scripts/train_rl.py --mode eval --model models/rl/best_model/best_model.zip --episodes 10
```

Metrics:
- Average return: mean total return per episode.
- Win rate: percent of episodes with positive return.
- Sharpe: risk-adjusted return.
- Max drawdown: worst equity drop.

Deployment tips:
WARNING: Do not enable RL on live trading before a small-capital test.

## 5. Integration With Existing System

- RL provides tactical position and strategy weights.
- Portfolio decision remains the baseline.
- RL can be disabled any time via `RL_ENABLED=false`.
- Backtest vs RL training: backtest focuses on strategy metrics, RL training optimizes reward.

## 6. Troubleshooting

- Model does not converge: lower learning rate or simplify reward.
- Live performance worse than backtest: reduce leverage and add transaction costs.
- Training errors: verify data integrity and TA-Lib install.

FAQ:
1) Q: Can I run RL without LLM? A: Yes, set `DECISION_MODE=rl_only`.
2) Q: How do I disable RL quickly? A: Set `RL_ENABLED=false`.
3) Q: Can I train on multiple symbols? A: Start with single symbol, then extend.

## 7. Advanced Topics

- Hyperparameter tuning with multiple seeds.
- Reward shaping with risk-aware penalties.
- Multi-asset training with separate envs.
- Online learning with rolling windows.

## 8. Best Practices

- Use a fixed training period and evaluate on out-of-sample data.
- Monitor drawdown and trading costs in reward.
- Retrain monthly or after regime changes.
- Keep logs and compare models before deploying.
