# Alpha Arena - 量化交易系统 (BTC 永续/OKX 模拟盘)

一个以数据库为核心、以 DataService 为唯一数据入口的量化交易系统。覆盖数据采集、策略库、回测、LLM 决策、多策略组合评分、风险控制、订单生命周期追踪、执行与前端可视化。

---

## 0. 数据层总领（Data-First Architecture）

- 数据入口：OKX → SQLite → DataService
- 业务层仅通过 DataService 读数据，禁止直接 SQL
- 前端/API 只读默认，写入需显式开启 `API_WRITE_ENABLED=true`

---

## 1. 环境准备

### 1.1 依赖安装
```bash
pip install -r requirements.txt
```

### 1.2 配置文件
```bash
copy .env.example .env
```

`.env` 必填项：
- OKX 模拟盘参数
- 数据库路径 `DATABASE_URL`
- LLM Provider（DeepSeek/OpenAI/Grok/Gemini/Ollama/vLLM）

### 1.3 目录结构（重点）
- `src/alpha_arena/data/`：DataService（统一读接口）
- `src/alpha_arena/strategies/`：策略库（已启用 3 个）
- `src/alpha_arena/decision/`：LLM 决策 + 组合评分
- `src/alpha_arena/execution/`：执行器、分配器、生命周期、订单跟踪
- `src/alpha_arena/risk/`：风控规则
- `src/alpha_arena/db/`：迁移脚本与连接
- `scripts/`：采集/回测/同步/交易循环/API/前端服务脚本
- `frontend/`：React 前端
- `架构设计/`：架构与数据库文档

---

## 2. 本地启动总览（Localhost Map）

所有服务默认跑在本机 `localhost`：
- API 服务：`http://127.0.0.1:8000`
- 前端 Dashboard：`http://127.0.0.1:5173`
- 前端 Backtest：`http://127.0.0.1:5173/backtest`
- 前端 Data Monitor：`http://127.0.0.1:5173/data-monitor`
- 数据库浏览器：`http://127.0.0.1:8001`

常用接口示例：
- `http://127.0.0.1:8000/api/market/candles?symbol=BTC/USDT:USDT&timeframe=1h&limit=10`
- `http://127.0.0.1:8000/api/decisions?symbol=BTC/USDT:USDT&limit=20`
- `http://127.0.0.1:8000/api/backtests`
- `http://127.0.0.1:8000/api/data-health/coverage?symbol=BTC/USDT:USDT`

---

## 3. 数据层（采集 + 数据库）

### 3.1 初始化/迁移
```bash
python scripts/db_migrate.py
```
升级后新增迁移时，同样运行该命令完成表结构更新。

### 3.2 历史数据采集
增量采集（从数据库最新时间点往后）：
```bash
python scripts/ingest_okx.py --since-days 365
python scripts/ingest_okx.py --symbol BTC/USDT:USDT --since-days 730 --timeframes 15m,1h,4h,1d
```

一次性历史回补（忽略 last_ts，适合大区间回补）：
```bash
python scripts/ingest_okx_backfill.py --symbol BTC/USDT:USDT --since-days 730 --timeframes 15m,1h,4h,1d
```

### 3.3 数据质量检查
```bash
python scripts/db_stats.py
```
报告输出：`reports/db_stats_YYYYMMDD.json`

### 3.4 缺口修复
```bash
python scripts/db_repair.py --symbol BTC/USDT:USDT --timeframe 15m
```

### 3.5 数据库浏览器（HTML）
```bash
python scripts/db_web_viewer.py --host 127.0.0.1 --port 8001
```
访问：`http://127.0.0.1:8001`

---

## 4. 数据服务层（DataService）

策略、回测、决策只通过 DataService 读取数据：
- `get_candles(symbol, timeframe, limit)`
- `get_latest_funding(symbol)`
- `get_latest_prices(symbol)`
- `get_latest_market_snapshot(...)`

测试：
```bash
python scripts/smoke_data_service.py --symbol BTC/USDT:USDT --timeframe 15m
```

---

## 5. 策略与回测层

### 5.1 已实现策略
- `ema_trend`
- `bollinger_range`
- `funding_rate_arbitrage`

策略验证：
```bash
python scripts/smoke_strategies.py --symbol BTC/USDT:USDT --timeframe 1h
```

### 5.2 回测 CLI（StrategyLibrary 版本）
```bash
python scripts/run_backtest_mvp.py --symbol BTC/USDT:USDT --timeframe 1h --strategy ema_trend --limit 2000 --signal-window 300 --initial-capital 10000 --fee-rate 0.0005
```

参数含义：
- `--symbol`: 交易对（默认读取 `.env` 的 `OKX_DEFAULT_SYMBOL`）
- `--timeframe`: 周期（常用：`15m`/`1h`/`4h`/`1d`）
- `--strategy`: 策略 ID（`ema_trend`/`bollinger_range`/`funding_rate_arbitrage`）
- `--limit`: 回测 K 线条数
- `--signal-window`: 策略信号窗口（必须 ≤ `limit`）
- `--initial-capital`: 初始资金（USDT）
- `--fee-rate`: 手续费比例（0.0005=0.05%）
- `--name`: 可选回测名称

结果落库：`backtest_configs` / `backtest_results` / `backtest_orders` / `backtest_decisions` / `backtest_runs`

### 5.3 回测前端工作台（/backtest）
启动 API + 前端后访问：
- `http://127.0.0.1:5173/backtest`

功能：
- 三段式布局：配置面板 / 图表面板（K线+权益曲线+回撤）/ 结果面板
- 12 项一级指标 + 二级诊断指标
- 多次回测对比（2~3 条权益曲线叠加）
- CSV 导出（equity_curve / trades / positions）

说明：滑点/下单方式/资金费等高级参数为前端建模字段，目前后端 MVP 仍只使用核心参数（symbol/timeframe/limit/fee/strategy）。

---

## 6. 决策层（LLM + 组合评分）

LLM 决策（单策略选择）：
```bash
python scripts/smoke_llm_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 100
```

多策略组合评分：
```bash
python scripts/smoke_portfolio_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

阈值可配置（`.env`）：
- `REGIME_ADX_THRESHOLD`
- `REGIME_BB_WIDTH_THRESHOLD`
- `PORTFOLIO_GLOBAL_LEVERAGE`
- `PORTFOLIO_DIFF_THRESHOLD`

---

## 7. 执行与风控层

单次交易循环（手动触发）：
```bash
python scripts/main_trading_loop.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor simulated --equity 10000
```

连续循环（每 15 分钟）：
```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200 --executor okx --equity 1000 --interval 900 --trade
```

说明：
- `--executor simulated` 为模拟撮合
- `--executor okx` 为真实 API 下单（模拟盘/实盘）
- 需要 `TRADING_ENABLED=true` 才会实际下单

订单状态说明：
`Order executed: <id> -> NEW` 表示订单已被交易所接收。

---

## 8. 同步与审计层

余额/持仓同步：
```bash
python scripts/sync_account.py
python scripts/sync_account.py --loop --interval 60
```

订单状态同步：
```bash
python scripts/sync_orders.py
python scripts/sync_orders.py --loop --interval 30
```

同步结果写入：
- `balances`
- `positions`
- `position_snapshots`
- `orders`
- `order_lifecycle_events`
- `risk_events`

---

## 9. 数据可观测性与数据健康

新增能力：
- 余额/持仓快照统一 USDT 口径（`balance_snapshots` / 扩展 `position_snapshots`）
- 订单审计增强（`order_lifecycle_events` 扩展 raw payload / exchange status）
- 回测指标版本化（`backtest_runs` 支持 `metrics_json`/`equity_curve_json`）
- K 线缺口/重复/修复记录（`candle_integrity_events` / `candle_repair_jobs`）
- 核心索引补齐，PostgreSQL 分区预留（详见 `MIGRATION_PLAN.md`）

前端面板：
- `http://127.0.0.1:5173/data-monitor`
- 展示 15m/1h/4h/1d 的覆盖范围与 K 线条数
- 支持 Scan/Repair（需 `API_WRITE_ENABLED=true`）

手动 API 示例（PowerShell）：
```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/data-health/scan -Method POST -ContentType "application/json" -Body '{\"symbol\":\"BTC/USDT:USDT\",\"timeframes\":[\"15m\",\"1h\"]}'
Invoke-WebRequest http://127.0.0.1:8000/api/data-health/repair -Method POST -ContentType "application/json" -Body '{\"symbol\":\"BTC/USDT:USDT\",\"timeframe\":\"15m\",\"range_start_ts\":1700000000000,\"range_end_ts\":1700003600000,\"mode\":\"refetch\"}'
```

---

## 10. API 服务（前端对接）

启动 API：
```bash
python scripts/api_server.py --host 127.0.0.1 --port 8000
```

读接口（示例）：
- `/api/market/candles`
- `/api/market/funding`
- `/api/market/prices`
- `/api/decisions`
- `/api/orders`
- `/api/trades`
- `/api/positions`
- `/api/balances`
- `/api/account/summary`
- `/api/backtests`
- `/api/backtests/{id}`
- `/api/health`
- `/api/data-health/coverage`
- `/api/data-health/integrity-events`

写接口（默认关闭）：
- `/api/actions/ingest`
- `/api/actions/sync_account`
- `/api/actions/sync_orders`
- `/api/backtest/run`
- `/api/data-health/scan`
- `/api/data-health/repair`

开启方式：`.env` 中 `API_WRITE_ENABLED=true`。

---

## 11. 前端（React + Vite）

启动前端：
```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

或使用 pnpm：
```bash
cd frontend
copy .env.example .env
pnpm install
pnpm dev
```

`.env` 中配置：
```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000
VITE_DASHBOARD_SYMBOL=BTC/USDT:USDT
VITE_DASHBOARD_TIMEFRAME=15m
VITE_DASHBOARD_LIMIT=200
```

页面入口：
- Dashboard：`http://127.0.0.1:5173`
- Backtest：`http://127.0.0.1:5173/backtest`
- Data Monitor：`http://127.0.0.1:5173/data-monitor`

Dashboard K线范围说明：
- 默认只拉 `VITE_DASHBOARD_LIMIT` 条 K 线（例如 15m*200 ≈ 2 天）
- 若要显示更长历史：可改 `VITE_DASHBOARD_TIMEFRAME=1d` 且 `VITE_DASHBOARD_LIMIT=1200`（约 3 年）
- 后端 `/api/market/candles` 单次上限 5000 条，15m 无法一口气展示 3 年（建议用 1d）

---

## 12. .env 关键参数说明（节选）

```ini
OKX_IS_DEMO=true
OKX_TD_MODE=cross
OKX_POS_MODE=long_short
TRADING_ENABLED=false
API_WRITE_ENABLED=false
DATABASE_URL=sqlite:///data/alpha_arena.db
RISK_MAX_NOTIONAL=20000
RISK_MAX_LEVERAGE=3
RISK_MIN_CONFIDENCE=0.6
```

- `OKX_POS_MODE=net` 时不需要 `posSide`
- `TRADING_ENABLED=false` 默认禁止实盘交易

---

## 13. 参考文档

- `架构设计/ARCHITECTURE.md`
- `架构设计/MULTI_AGENT_ARCHITECTURE.md`
- `架构设计/DB_OVERVIEW.md`
- `架构设计/DB_PLAN.md`
- `FRONTEND_PLAN.md`
- `plan.md`
- `MIGRATION_PLAN.md`
- `API_DOCS.md`

---

## 14. 下一步建议

- 加入更细粒度订单撮合（滑点/部分成交）
- 完善回测成本与资金费模型
- 强化学习模块先占位，后续再接入
