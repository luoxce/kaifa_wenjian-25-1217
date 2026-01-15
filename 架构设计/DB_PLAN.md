# Alpha Arena - 数据库规划（DB Plan）

> **版本**: v1.0  
> **更新日期**: 2026-01-12  
> **范围**: BTC/USDT 永续（OKX 模拟盘），SQLite 起步，后续迁移 PostgreSQL

---

## 1. 目标与约束

- **先 SQLite，后 PostgreSQL**：结构保持可迁移，避免 SQLite 专有语法  
- **时间统一**：`timestamp` 使用 UTC 毫秒  
- **数值类型**：价格/数量优先使用 `NUMERIC`（兼容迁移）  
- **唯一键与索引齐全**：防重复、加速查询  
- **v1 仅存 15m / 1h / 4h / 1d**：避免过早引入高频成本  
- **订单簿不入库**：先存 OHLCV + funding + mark/index/last  

---

## 2. 数据域清单

### 2.1 市场数据
- `market_data`：OHLCV（15m/1h/4h/1d）
- `funding_rates`：资金费率
- `price_snapshots`：mark/index/last
- `open_interest`：未平仓量（可选）
- `long_short_ratio`：多空比（可选）

### 2.2 交易与风控
- `orders`：订单
- `order_lifecycle_events`：订单状态流
- `trades`：成交
- `positions`：当前持仓
- `position_snapshots`：持仓快照
- `balances`：账户余额快照
- `risk_events`：风控事件

### 2.3 LLM 与决策
- `prompt_versions`：Prompt 版本
- `model_versions`：模型版本
- `llm_runs`：LLM 调用记录
- `decisions`：策略决策记录

### 2.4 回测
- `backtest_configs`：回测配置
- `backtest_results`：回测结果
- `backtest_orders` / `backtest_positions` / `backtest_decisions`

### 2.5 运行与采集
- `ingestion_runs`：采集运行记录
- `schema_version`：迁移版本

---

## 3. Schema 设计原则

- **数据分层**：市场原始数据与交易/风控分表  
- **可追溯**：订单→成交→持仓快照 → 风控事件  
- **可审计**：决策与 LLM 调用记录可追踪  
- **可回测**：回测与实盘数据隔离存储  

---

## 4. 迁移机制

- v1 采用 **版本化 SQL**（目录：`src/alpha_arena/db/migrations`）  
- `schema_version` 记录已应用迁移  
- 迁移入口：`scripts/db_migrate.py`  
- 后续可平滑升级至 Alembic（SQLite batch mode）  

---

## 5. OKX 数据采集策略

### 5.1 OHLCV
- 目标时间框架：15m/1h/4h/1d  
- 先查 DB 最新时间戳，再增量拉取  
- `ON CONFLICT` 去重，避免重复插入  

### 5.2 衍生指标
- 每次采集时同时写入：  
  - `funding_rates`  
  - `price_snapshots`  
  - `open_interest`（如果可用）  

---

## 6. 未来扩展

- 需要更细粒度执行 → 补 1m  
- 订单簿信号 → 先存派生指标（best bid/ask, spread）  
- 生产切 PostgreSQL → 保持 schema 不变，仅迁移数据  

---

**本计划为数据库与采集系统的真源文档。**

## 7. DataService (read-only access layer)
- Business modules must read data via DataService; SQL is only allowed inside ingest/DB tooling.
- DataService maps table columns to standard fields and returns normalized DataFrames/snapshots.
- Smoke test: `python scripts/smoke_data_service.py`.
