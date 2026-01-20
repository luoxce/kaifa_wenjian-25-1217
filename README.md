# Alpha Arena - 量化交易系统 (BTC 永续/OKX 模拟盘)

以数据库为核心、以 DataService 为唯一数据入口的量化交易系统。覆盖数据采集、策略库、回测、LLM 决策（多策略组合）、组合评分、风险控制、订单生命周期追踪、执行与前端可视化。

---

## 0. 一步一步启动（Quick Start）

> 默认 Windows / PowerShell。Linux/Mac 同理替换为对应命令。

1) 创建虚拟环境并安装依赖：
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) 准备配置：
```bash
copy .env.example .env
```
编辑 `.env`，至少补齐：
`DATABASE_URL`、`OKX_*`、`LLM_PROVIDER` 与对应的 `*_API_KEY`。

3) 初始化数据库：
```bash
python scripts/db_migrate.py
```

4) 采集历史数据（示例）：
```bash
python scripts/ingest_okx.py --symbol BTC/USDT:USDT --since-days 365 --timeframes 15m,1h,4h,1d
```

5) 快速验证数据与策略：
```bash
python scripts/smoke_data_service.py --symbol BTC/USDT:USDT --timeframe 1h
python scripts/smoke_strategies.py --symbol BTC/USDT:USDT --timeframe 1h
python scripts/test_new_strategies.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

6) 回测（CLI）：
```bash
python scripts/run_backtest_mvp.py --symbol BTC/USDT:USDT --timeframe 1h --strategy ema_trend --limit 2000 --signal-window 300 --initial-capital 10000 --fee-rate 0.0005
```

7) LLM 决策 / 组合评分：
```bash
python scripts/smoke_llm_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 100
python scripts/smoke_portfolio_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

8) 单次交易循环（模拟）：
```bash
python scripts/main_trading_loop.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --equity 10000
```

9) 启动 API：
```bash
python scripts/api_server.py --host 127.0.0.1 --port 8000
```

10) 启动前端：
```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

前端访问：
- Dashboard: `http://127.0.0.1:5173`
- Backtest: `http://127.0.0.1:5173/backtest`
- Data Monitor: `http://127.0.0.1:5173/data-monitor`

---

## 1. 数据层总领（Data-First Architecture）

- 数据入口：OKX → SQLite → DataService
- 业务层仅通过 DataService 读数据，禁止直接 SQL
- API 默认只读，写入需显式开启 `API_WRITE_ENABLED=true`

---

## 2. 目录结构（功能分层入口）

- `src/alpha_arena/data/`：数据读取入口（DataService）
- `src/alpha_arena/strategies/`：策略库（含新策略）
- `src/alpha_arena/decision/`：LLM 决策、多策略组合、反馈分析
- `src/alpha_arena/execution/`：执行器、分配器、订单跟踪
- `src/alpha_arena/risk/`：风控规则
- `src/alpha_arena/db/`：迁移与连接
- `scripts/`：采集/回测/同步/交易循环/API 脚本
- `frontend/`：React 前端
- `docs/`、`架构设计/`：架构与数据库文档

---

## 3. 数据层（采集 + 数据库）

### 3.1 初始化/迁移
```bash
python scripts/db_migrate.py
```

### 3.2 历史数据采集
增量采集：
```bash
python scripts/ingest_okx.py --since-days 365
```

一次性回补：
```bash
python scripts/ingest_okx_backfill.py --symbol BTC/USDT:USDT --since-days 730 --timeframes 15m,1h,4h,1d
```

### 3.3 数据质量检查与修复
```bash
python scripts/db_stats.py
python scripts/db_repair.py --symbol BTC/USDT:USDT --timeframe 15m
```

### 3.4 数据库浏览器
```bash
python scripts/db_web_viewer.py --host 127.0.0.1 --port 8001
```
访问：`http://127.0.0.1:8001`

---

## 4. DataService 层

统一数据入口：
- `get_ohlcv(symbol, timeframe, limit)`
- `get_candles_range(symbol, timeframe, start_ts, end_ts)`
- `get_latest_funding(symbol)`
- `get_latest_prices(symbol)`

测试：
```bash
python scripts/smoke_data_service.py --symbol BTC/USDT:USDT --timeframe 1h
```

---

## 5. 策略层（Strategy）

### 5.1 已实现策略（含新策略）
- `ema_trend`（趋势）
- `bollinger_range`（震荡）
- `funding_rate_arbitrage`（资金费率）
- `breakout`（突破）
- `grid_trading`（网格）
- `momentum`（动量）
- `mean_reversion`（均值回归）

启用策略：`src/alpha_arena/strategies/registry.py` 中将 `enabled=True`。

### 5.2 策略参数（默认值）

- `ema_trend`
  - `ema_fast=9`, `ema_medium=21`, `ema_slow=55`
  - `atr_period=14`, `stop_loss_atr=2.0`, `take_profit_atr=4.0`
  - `max_position=0.20`, `max_leverage=3`
  - `rsi_min=50`, `rsi_max=70`, `rsi_short_min=30`, `rsi_short_max=50`
  - `volume_threshold=1.2`

- `bollinger_range`
  - `bb_period=20`, `bb_std=2.0`
  - `rsi_oversold=35`, `rsi_overbought=65`
  - `bandwidth_max=0.04`, `touch_threshold=1.005`
  - `stop_loss_pct=0.02`
  - `max_position=0.25`, `max_leverage=2`

- `funding_rate_arbitrage`
  - `min_funding_rate=0.001`, `exit_funding_rate=0.0005`
  - `min_duration=3`, `history_window=10`
  - `max_position=0.50`, `max_leverage=1`

- `breakout`
  - `lookback_period=20`, `breakout_threshold=1.002`
  - `volume_threshold=1.5`
  - `atr_period=14`, `stop_loss_atr=2.0`, `take_profit_atr=4.0`
  - `max_position=0.25`, `max_leverage=3`

- `grid_trading`
  - `grid_count=5`, `grid_range=0.04`
  - `bb_period=20`, `bb_std=2.0`
  - `position_per_grid=0.05`
  - `max_position=0.30`, `max_leverage=2`

- `momentum`
  - `momentum_period=14`, `price_momentum_threshold=0.05`
  - `volume_momentum_threshold=1.3`
  - `rsi_period=14`, `rsi_momentum_threshold=5`
  - `atr_period=14`, `stop_loss_atr=2.5`, `take_profit_atr=5.0`
  - `max_position=0.20`, `max_leverage=3`

- `mean_reversion`
  - `ma_period=20`, `std_period=20`
  - `entry_std=2.0`, `exit_std=0.5`
  - `rsi_period=14`, `rsi_oversold=30`, `rsi_overbought=70`
  - `stop_loss_pct=0.03`
  - `max_position=0.25`, `max_leverage=2`

### 5.3 策略验证
```bash
python scripts/smoke_strategies.py --symbol BTC/USDT:USDT --timeframe 1h --include-disabled
python scripts/test_new_strategies.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

### 5.4 回测（CLI / API / 前端）
CLI 回测：
```bash
python scripts/run_backtest_mvp.py --symbol BTC/USDT:USDT --timeframe 1h --strategy ema_trend --limit 2000 --signal-window 300 --initial-capital 10000 --fee-rate 0.0005
```

API 回测（需 `API_WRITE_ENABLED=true`）：
- `POST /api/backtest/run`

前端回测：
- `http://127.0.0.1:5173/backtest`

说明：
- 回测使用历史 K 线，策略参数在回测请求中传入。
- 当前回测未接入 RL 模型（见第 14 章）。

---

## 6. 决策层（LLM + 组合评分）

### 6.1 LLM 多策略输出
LLM 输出结构（关键字段）：
```json
{
  "market_regime": "TREND",
  "strategy_allocations": [
    {"strategy_id": "ema_trend", "weight": 0.6, "confidence": 0.85, "reasoning": "trend"},
    {"strategy_id": "momentum", "weight": 0.3, "confidence": 0.75, "reasoning": "momentum"},
    {"strategy_id": "breakout", "weight": 0.1, "confidence": 0.65, "reasoning": "breakout"}
  ],
  "total_position": 0.8,
  "confidence": 0.8,
  "reasoning": "multi-strategy blend"
}
```
校验规则：
- `strategy_allocations` 权重和需 ~1.0（±0.05）
- `strategy_id` 必须在启用策略列表
- `total_position` ∈ [-1, 1]（并受 `PORTFOLIO_GLOBAL_LEVERAGE` 限制）
- 兼容 fallback：`selected_strategy_id` 或 `HOLD`

### 6.2 市场环境识别（Regime）
新增指标：
- `ATR_Percentile`（波动率百分位）
- `Price_Efficiency`（趋势效率）
- `Volume_Trend`（成交量趋势）

识别类型：
`STRONG_TREND / WEAK_TREND / RANGE / BREAKOUT / HIGH_VOLATILITY / LOW_VOLATILITY`

LLM prompt 中包含：
`market_regime_context.current` + 最近 5 个周期历史 + 指标信号。

### 6.3 决策反馈（Feedback）
系统自动统计最近 N 次决策的：
胜率、平均收益、最佳/最差策略与市场环境，并附加到 LLM 提示词。

---

## 7. 组合评分层（Portfolio Decision）

- `PortfolioDecisionEngine` 基于 Regime + 回测表现给策略打分
- 规则：`regime_score` + `performance_score`
- 输出 `allocations`（权重 + 评分）

示例：
```bash
python scripts/smoke_portfolio_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

---

## 8. 执行与风控层

单次交易循环：
```bash
python scripts/main_trading_loop.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --equity 10000
```

连续循环：
```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --interval 900
```

### 8.1 模拟盘运行（两种模式）
本地模拟撮合（不触碰交易所）：
```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --interval 900
```

OKX 模拟盘（真实交易所接口，Demo 环境）：
```ini
OKX_IS_DEMO=true
TRADING_ENABLED=true
```
```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor okx --interval 900 --trade
```

### 8.2 实盘运行（OKX）
```ini
OKX_IS_DEMO=false
TRADING_ENABLED=true
```
```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor okx --interval 900 --trade
```

### 8.3 一键启动（模拟盘 4 进程）
```bash
powershell -ExecutionPolicy Bypass -File scripts/start_paper_trading.ps1 -Symbol BTC/USDT:USDT -Timeframe 1h -IngestTimeframes 1h -Executor okx -Trade 1
```

LLM 决策模式（需配置 `LLM_PROVIDER` 与对应 API Key）：
```bash
powershell -ExecutionPolicy Bypass -File scripts/start_paper_trading.ps1 -Symbol BTC/USDT:USDT -Timeframe 1h -IngestTimeframes 1h -Executor okx -Trade 1 -DecisionMode llm
```

说明：
- 脚本会分别启动 4 个 PowerShell 窗口：K 线补数、交易循环、账户同步、订单/成交同步。
- 如果使用虚拟环境，可传入 `-Python .\\.venv\\Scripts\\python.exe`
- 要降低交易同步负载，可用 `-OrderSyncMode open`
- 一键脚本默认使用账户余额快照，不传 `--equity`
- 如需固定权益值，直接运行 `trading_daemon.py` 时可加 `--equity`

注意：
- `trading_daemon.py` 会检查 `TRADING_ENABLED=true` 才会下单。
- `main_trading_loop.py` 是单次循环，不做 `TRADING_ENABLED` 检查，请谨慎使用实盘。

关键参数（`.env`）：
- `TRADING_ENABLED`
- `RISK_MAX_NOTIONAL`
- `RISK_MAX_LEVERAGE`
- `RISK_MIN_CONFIDENCE`

---

## 9. 同步与审计层

```bash
python scripts/sync_account.py
python scripts/sync_orders.py
```

写入表：
`balances` / `positions` / `orders` / `trades` / `order_lifecycle_events` 等。

---

## 10. 数据可观测性与数据健康

- 数据健康面板：`/data-monitor`
- 扫描/修复需 `API_WRITE_ENABLED=true`

---

## 11. API 服务

启动：
```bash
python scripts/api_server.py --host 127.0.0.1 --port 8000
```

核心读接口（节选）：
- `/api/market/candles`
- `/api/market/funding`
- `/api/decisions`
- `/api/orders` / `/api/trades` / `/api/positions`
- `/api/backtests`
- `/api/data-health/coverage`

写接口需开启：`API_WRITE_ENABLED=true`

---

## 12. 前端（Dashboard / Backtest / Data Monitor）

当前前端主要覆盖：
- Dashboard：行情 + 订单 + 决策流
- Backtest：回测配置 + 结果 + 曲线
- Data Monitor：覆盖率 + 缺口扫描 + 修复

提示：LLM 多策略分配、反馈摘要、Regime 历史等当前未在前端展示，需新增 API 字段与 UI 模块对接。

---

## 13. .env 关键参数（节选）

```ini
DATABASE_URL=sqlite:///data/alpha_arena.db
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
REGIME_ADX_THRESHOLD=25
REGIME_BB_WIDTH_THRESHOLD=0.04
PORTFOLIO_GLOBAL_LEVERAGE=1.0
PORTFOLIO_DIFF_THRESHOLD=10
PORTFOLIO_MIN_NOTIONAL=10
OKX_IS_DEMO=true
TRADING_ENABLED=false
API_WRITE_ENABLED=false
RISK_MAX_NOTIONAL=20000
RISK_MAX_LEVERAGE=3
RISK_MIN_CONFIDENCE=0.6
```

---

## 14. 强化学习（RL）

可选模块（PPO + TradingEnv），脚本：
```bash
python scripts/train_rl.py --mode train --config configs/rl_config_fast.json
```

启用：
```ini
RL_ENABLED=true
RL_MODEL_PATH=models/rl/best_model/best_model.zip
RL_CONFIDENCE_THRESHOLD=0.7
```

### 14.1 RL 用于模拟盘 / 实盘
本地模拟撮合（RL 参与组合调整）：
```bash
python scripts/main_trading_loop.py --use-rl --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --equity 10000
```

OKX 模拟盘（Demo）：
```ini
OKX_IS_DEMO=true
TRADING_ENABLED=true
```
```bash
python scripts/main_trading_loop.py --use-rl --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor okx --equity 10000
```

OKX 实盘：
```ini
OKX_IS_DEMO=false
TRADING_ENABLED=true
```
```bash
python scripts/main_trading_loop.py --use-rl --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor okx --equity 10000
```

说明：
- RL 目前集成在 `main_trading_loop.py` 的单次循环中，用于对组合决策做调整。
- 若需要 RL 的持续交易，请扩展 `trading_daemon.py`（当前未接入 RL）。

### 14.2 RL 用于回测
当前回测引擎未集成 RL。若需要 RL 回测，需要把 RL 策略/决策逻辑接入 `scripts/run_backtest_mvp.py` 的信号生成流程。

---

## 15. 参考文档

- `API_DOCS.md`
- `docs/RL_MODULE_GUIDE.md`
- `架构设计/ARCHITECTURE.md`
- `架构设计/DB_OVERVIEW.md`
- `FRONTEND_PLAN.md`
