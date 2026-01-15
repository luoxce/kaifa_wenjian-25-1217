# Alpha Arena - 数据库说明（SQLite v1）

> **版本**: v1.0  
> **更新日期**: 2026-01-12  
> **适用阶段**: 本地开发 / 回测 / 模拟盘  

---

## 1. 当前状态

- 已完成数据库初始化（`python scripts/db_migrate.py`）
- 已完成 OKX 历史数据采集（示例：30 天 15m/1h/4h/1d）
- 数据已落库到本地 SQLite

---

## 2. 数据库存放位置

- 由 `.env` 的 `DATABASE_URL` 控制  
- 默认值：`sqlite:///data/alpha_arena.db`  
- **结论**：采集完成即写入本地文件数据库

---

## 3. 设计目标（摘要）

- 可迁移：SQLite → PostgreSQL  
- 时间统一：`timestamp` 为 UTC 毫秒  
- 数值统一：价格/数量使用 `NUMERIC`  
- 去重可靠：关键唯一键 + 索引  
- v1 只存 15m/1h/4h/1d  
- v1 不存全量订单簿（仅衍生指标）

详细规划见：`架构设计/DB_PLAN.md`

---

## 4. 数据表清单（分域）

### 4.1 市场数据
- `market_data`：OHLCV（15m/1h/4h/1d）
- `funding_rates`：资金费率
- `price_snapshots`：last/mark/index 价格快照
- `open_interest`：未平仓量（可能为空）
- `long_short_ratio`：多空比（可选）

### 4.2 交易与风控
- `orders`：订单
- `order_lifecycle_events`：订单状态流
- `trades`：成交
- `positions`：当前持仓
- `position_snapshots`：持仓快照
- `balances`：账户余额快照
- `risk_events`：风控事件

### 4.3 决策与 LLM
- `prompt_versions`：Prompt 版本
- `model_versions`：模型版本
- `llm_runs`：LLM 调用记录
- `decisions`：策略决策记录

### 4.4 回测
- `backtest_configs`：回测配置
- `backtest_results`：回测结果
- `backtest_orders` / `backtest_positions` / `backtest_decisions`

### 4.5 运行与采集
- `ingestion_runs`：采集运行记录
- `schema_version`：迁移版本表

---

## 5. 数据是如何进入数据库的？

1. 执行采集脚本：`python scripts/ingest_okx.py`
2. 脚本会调用 OKX 公共接口拉取 OHLCV + 衍生数据  
3. 数据经过去重后写入本地 SQLite  
4. 采集运行记录写入 `ingestion_runs`

---

## 6. 能存哪些数据？

**可以存储：**
- 历史 K 线、资金费率、mark/index/last 价格
- 决策记录、订单/成交、持仓快照、风控事件
- 回测配置与回测结果

**当前不存：**
- 全量订单簿深度（数据量过大）
- 高频 1s/5s 行情（后续再扩展）

---

## 7. 常用排查

- 采集是否写入：查 `ingestion_runs` 与 `market_data`  
- 某周期是否齐全：按 `symbol + timeframe` 统计条数  
- OKX 接口超时：确认代理与网络连通性

---

## 8. 后续扩展

- 增加 1m K 线（提升回测精度）
- 衍生订单簿指标（best bid/ask、spread）
- PostgreSQL 替换 SQLite，保持 schema 不变

---

**结论**：数据库已经可用，采集完成即写入本地 SQLite 文件。
