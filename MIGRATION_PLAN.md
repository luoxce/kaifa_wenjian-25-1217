# Migration Plan (Observability + Integrity + Audit Upgrade)

目标：在不破坏现有交易/回测逻辑的前提下，扩展数据库可观测性、审计能力、指标版本化与数据完整性追踪。SQLite 先落地，字段设计兼容 PostgreSQL。

## 已有迁移
- `001_init.sql`：基础表结构
- `002_order_fill_fields.sql`：orders 的成交字段补充

## 新增迁移（本次）
1. `003_add_balance_position_snapshots.sql`
   - 新增 `balance_snapshots`
   - 扩展 `position_snapshots`（exchange/account_id/qty/usdt 口径/raw_payload）

2. `004_extend_order_lifecycle_events_audit_fields.sql`
   - 扩展 `order_lifecycle_events` 审计字段（exchange_status/raw_payload/fill 明细等）
   - 增加审计索引

3. `005_extend_backtest_runs_json_versioning.sql`
   - 新增 `backtest_runs`，支持 `metrics_json` / `equity_curve_json` + `schema_version`

4. `006_add_candle_integrity_events_and_repair_jobs.sql`
   - 新增 `candle_integrity_events` + `candle_repair_jobs`
   - 记录缺口/重复/修复事件

5. `007_add_indexes_and_perf_improvements.sql`
   - 核心表索引补齐（orders/trades/market_data/backtest）

## PostgreSQL 迁移预留（设计）
- JSON 字段在 SQLite 存 TEXT，迁移到 PG 后可改为 JSONB
- 分区建议：
  - `market_data`：按 `symbol` + `timeframe` + 月分区
  - `trades` / `order_lifecycle_events`：按月分区
  - `candle_integrity_events`：按月分区

## 回滚策略
- 本迁移仅新增表/字段与索引，不删除旧字段
- 如需回滚，优先保留表结构，业务代码可忽略新增列
