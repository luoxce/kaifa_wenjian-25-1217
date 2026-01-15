# Alpha Arena Delivery Plan

Goal: move from "single-pass demo" to a reliable, repeatable trading system.

## Current baseline (already working)
- SQLite DB + migrations + OKX OHLCV ingest
- DataService read layer
- StrategyLibrary + backtest MVP
- LLM decision (single + portfolio)
- PortfolioAllocator + main_trading_loop
- OKX order submit + fill polling + account sync

## Phase 1: Reliability foundation
1) Add a dedicated account sync script (balances/positions) and cron-ready loop.
   - Deliverable: `scripts/sync_account.py` (manual) + optional scheduler.
   - Acceptance: running the script updates `balances`, `positions`, `position_snapshots`.

2) Harden order fill tracking (partial fills, cancel, retry).
   - Deliverable: order refresh loop (per order) + partial fill support.
   - Acceptance: `orders` + `order_lifecycle_events` show correct transitions.

## Phase 2: Risk & guardrails
3) Add portfolio-level risk limits (daily loss, max open orders, cooldown).
   - Deliverable: new RiskRules + `.env` knobs.
   - Acceptance: violating rules blocks orders + writes `risk_events`.

4) Add "kill switch" and environment safety checks.
   - Deliverable: `TRADING_ENABLED` + sanity checks before sending orders.
   - Acceptance: when disabled, orders are created but never sent.

## Phase 3: Execution realism
5) Improve execution model in backtest (slippage + partial fills).
   - Deliverable: backtest engine enhancements + config knobs.
   - Acceptance: backtest results include realistic fees/slippage.

6) Add multi-order allocation (per strategy, not just net position).
   - Deliverable: allocator splits orders by strategy weight.
   - Acceptance: `orders` table shows multiple child orders per cycle.

## Phase 4: Observability & ops
7) Add structured logging + run IDs across decision/allocation/execution.
   - Deliverable: consistent run_id in `decisions` and `orders`.
   - Acceptance: full audit trail for any trade.

8) Add basic monitoring endpoints or CLI health summary.
   - Deliverable: `scripts/health_check.py`.
   - Acceptance: one command reports DB status, last sync, last trade.

## Phase 5: Strategy iteration loop
9) Automate backtest batch runs + performance ranking.
   - Deliverable: `scripts/run_backtest_batch.py`.
   - Acceptance: daily/weekly summary table for strategy selection.

10) Expand strategy set gradually + A/B compare.
   - Deliverable: enable 1-2 new strategies at a time.
   - Acceptance: each new strategy has backtest + live shadow run.

## Working mode
- We will implement Phase 1 first, then move to Phase 2, etc.
- Each step ends with a short smoke test + README update.
