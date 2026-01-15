# Alpha Arena - 量化交易系统 (BTC 永续/OKX 模拟盘)

一个以数据库为核心、以 DataService 为唯一数据入口的量化交易系统。覆盖数据采集、策略库、回测、LLM 决策、多策略组合评分、风险控制、订单生命周期追踪、执行与前端可视化。

---

## 1. 核心能力一览

- 数据层：OKX 历史数据采集 + SQLite 数据库 + 数据质量检查/修复
- 数据服务层：`DataService` 统一读取（业务层禁止直接 SQL）
- 策略层：EMA 趋势 / 布林震荡 / 资金费率套利（可扩展）
- 决策层：LLM 策略选择 + 多策略组合评分（可配置阈值）
- 回测：最小闭环回测，结果落库
- 交易执行：模拟/OKX 执行器，订单生命周期与风控拦截
- 同步与审计：余额/持仓同步，订单状态跟踪
- 前端：Vite + React + Shadcn/ui + Lightweight Charts

---

## 2. 目录结构（重点）
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

## 3. 快速开始（Python）

### 3.1 安装与配置

```bash
pip install -r requirements.txt
copy .env.example .env
```

`.env` 必填项：
- OKX 模拟盘参数
- 数据库路径 `DATABASE_URL`
- LLM Provider（DeepSeek/OpenAI/Grok/Gemini/Ollama/vLLM）

### 3.2 初始化数据库

```bash
python scripts/db_migrate.py
```

### 3.3 拉取历史数据（OHLCV/资金费率/快照）

```bash
python scripts/ingest_okx.py --since-days 365
```

### 3.4 数据质量检查（推荐每次采集后跑）

```bash
python scripts/db_stats.py
```

报告输出：`reports/db_stats_YYYYMMDD.json`

### 3.5 数据修复（发现缺口后补齐）

```bash
python scripts/db_repair.py --symbol BTC/USDT:USDT --timeframe 15m
```

---

## 4. 数据服务层（DataService）

策略、回测、决策 **只能通过 DataService 读取数据**：

- `get_candles(symbol, timeframe, limit)`
- `get_latest_funding(symbol)`
- `get_latest_prices(symbol)`
- `get_latest_market_snapshot(...)`

测试：

```bash
python scripts/smoke_data_service.py --symbol BTC/USDT:USDT --timeframe 15m --limit 300
```

---

## 5. 策略库与回测 MVP

### 已实现策略
- `ema_trend`
- `bollinger_range`
- `funding_rate_arbitrage`

策略验证：

```bash
python scripts/smoke_strategies.py --symbol BTC/USDT:USDT --timeframe 1h
```

### 回测（StrategyLibrary 版本）

```bash
python scripts/run_backtest_mvp.py --symbol BTC/USDT:USDT --timeframe 1h --strategy ema_trend --limit 2000 --signal-window 300 --initial-capital 10000 --fee-rate 0.0005

```

参数含义：
- `--symbol`: 交易对（默认读取 `.env` 的 `OKX_DEFAULT_SYMBOL`）
- `--timeframe`: 周期（常用：`15m`/`1h`/`4h`/`1d`）
- `--strategy`: 策略 ID（当前可用：`ema_trend`/`bollinger_range`/`funding_rate_arbitrage`）
- `--limit`: 回测 K 线条数（越大越慢，且不能超过数据库已有数据量）
- `--signal-window`: 策略单次信号窗口大小（必须 ≤ `limit`）
- `--initial-capital`: 初始资金（USDT）
- `--fee-rate`: 手续费比例（0.0005=0.05%）
- `--name`: 可选回测名称（保存到 `backtest_configs`）

回测结果会写入：`backtest_configs` / `backtest_results` / `backtest_orders` / `backtest_decisions`

---

## 6. 决策层（LLM + 组合评分）

### LLM 决策（单策略选择）

```bash
python scripts/smoke_llm_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 100
```

输出内容落库到 `decisions` 表。

### 多策略组合评分

```bash
python scripts/smoke_portfolio_decision.py --symbol BTC/USDT:USDT --timeframe 1h --limit 200
```

阈值可配置（`.env`）：
- `REGIME_ADX_THRESHOLD`
- `REGIME_BB_WIDTH_THRESHOLD`
- `PORTFOLIO_GLOBAL_LEVERAGE`
- `PORTFOLIO_DIFF_THRESHOLD`

---

## 7. 执行层与风控

### 单次交易循环（手动触发）

```bash
python scripts/main_trading_loop.py --symbol BTC/USDT:USDT --timeframe 1h  --limit 200 --executor simulated --equity 10000
```

说明：
- `--executor simulated` 为模拟撮合
- `--executor okx` 为真实 API 下单（模拟盘/实盘）
- `--dry-run` 仅计算不下单

### 连续循环（每 15 分钟）

```bash
python scripts/trading_daemon.py --symbol BTC/USDT:USDT --timeframe 1h \
  --limit 200 --executor okx --equity 1000 --interval 900 --trade
```

`--trade` + `TRADING_ENABLED=true` 才会真正下单。

### 订单状态说明
`Order executed: <id> -> NEW` 表示订单已被交易所接收，若开启 `OKX_WAIT_FILL=true` 会自动轮询直到 `FILLED`。

---

## 8. 账户与订单同步（可靠性基石）

### 余额/持仓同步

```bash
python scripts/sync_account.py
python scripts/sync_account.py --loop --interval 60
```

### 订单状态同步

```bash
python scripts/sync_orders.py
python scripts/sync_orders.py --loop --interval 30
```

同步结果会写入：
- `balances`
- `positions`
- `position_snapshots`
- `orders`
- `order_lifecycle_events`
- `risk_events`

---

## 9. API 服务（前端对接）

### 稳定 API（推荐）

```bash
python scripts/api_server.py --host 127.0.0.1 --port 8000
```

读接口：
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

浏览器直接访问示例：
- `http://127.0.0.1:8000/api/balances`
- `http://127.0.0.1:8000/api/market/candles?symbol=BTC/USDT:USDT&timeframe=1h&limit=10`
- `http://127.0.0.1:8000/api/decisions?symbol=BTC/USDT:USDT&limit=20`
- `http://127.0.0.1:8000/api/backtests`

说明：根路径 `/` 没有页面，访问会返回 404。

写接口（默认关闭）：
- `/api/actions/ingest`
- `/api/actions/sync_account`
- `/api/actions/sync_orders`
- `/api/backtest/run`

开启方式：`.env` 中 `API_WRITE_ENABLED=true`。

### 数据库浏览器（HTML）

```bash
python scripts/db_web_viewer.py --host 127.0.0.1 --port 8001
```

---

## 10. 前端（React + Vite）

```bash
cd frontend
#copy .env.example .env
#npm install
npm run dev
```

`.env` 中配置：
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

前端回测面板（Backtest）说明：
- 需先启动 `scripts/api_server.py`
- 想在 UI 里点击 “Run Backtest”，需 `.env` 中设置 `API_WRITE_ENABLED=true` 并重启 API
- 面板入口：底部 Tabs 的 `Backtest`
- 运行后结果会出现在 `Recent Backtests`

---

## 11. .env 关键参数说明（节选）

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

## 12. 参考文档

- `架构设计/ARCHITECTURE.md`
- `架构设计/MULTI_AGENT_ARCHITECTURE.md`
- `架构设计/DB_OVERVIEW.md`
- `架构设计/DB_PLAN.md`
- `FRONTEND_PLAN.md`
- `plan.md`

---

## 13. 下一步建议

- 完善前端回测参数选择与历史结果可视化
- 加入更细粒度订单撮合（滑点/部分成交）
- 强化学习模块先占位，后续再接入
