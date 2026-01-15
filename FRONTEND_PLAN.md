# Frontend Plan (React) - Alpha Arena

Goal: build a React frontend that adapts to the current data interfaces
and provides a reliable UI for monitoring market data, decisions, orders,
and account state.

## Constraints and current state
- Data source is SQLite + DataService (Python).
- Existing HTTP API is `scripts/db_web_viewer.py` (FastAPI) with:
  - `GET /api/tables`
  - `GET /api/table/{table}?limit=50&offset=0`
- Trading loop and account sync are CLI-based today.

We need a thin API layer to make frontend data stable and typed.

## Phase 1: Backend API adapter (required for React)
Create/extend a FastAPI service that wraps DataService and DB access.

Option A (fast): extend `scripts/db_web_viewer.py`
- Add read-only endpoints:
  - `GET /api/market/candles?symbol=&timeframe=&limit=`
  - `GET /api/market/funding?symbol=`
  - `GET /api/market/prices?symbol=`
  - `GET /api/decisions?symbol=&limit=`
  - `GET /api/orders?symbol=&limit=`
  - `GET /api/trades?symbol=&limit=`
  - `GET /api/positions?symbol=`
  - `GET /api/balances?currency=`
  - `GET /api/health` (last sync, last trade, db status)

Option B (cleaner): add `scripts/api_server.py` (FastAPI)
- Use DataService for market endpoints.
- Use sqlite read helpers for orders/trades/positions/balances.
- Keep db_web_viewer for raw table browsing.

Acceptance:
- All endpoints return JSON with stable fields.
- CORS enabled for localhost React dev server.

## Phase 2: React app scaffolding
Tech stack (suggested):
- React + Vite + TypeScript
- UI: Ant Design or Radix + Tailwind
- Charts: ECharts or Recharts
- Data fetching: TanStack Query

Deliverable:
- `frontend/` workspace with base layout and routing.

## Phase 3: Core pages (read-only)
1) Dashboard
   - Total equity, unrealized PnL, last trade, last decision.
2) Market
   - Candle chart (OHLCV), funding rate, last/mark/index.
3) Strategy Decisions
   - Latest LLM/portfolio decisions and confidence.
4) Orders & Trades
   - Orders table + trades table with status badges.
5) Positions
   - Active positions + snapshots over time.
6) Risk & Events
   - Risk events + order lifecycle events.

Acceptance:
- Each page loads data from API and renders within 2s locally.

## Phase 4: Live refresh and UX polish
- Polling intervals (5s to 60s based on page).
- Error banners and empty states.
- Timezone handling (UTC vs local).

## Phase 5: Optional controls (write operations)
If needed later, add safe endpoints:
- POST `/api/actions/sync_account` (trigger sync)
- POST `/api/actions/sync_orders`
- POST `/api/actions/run_cycle` (single trading loop)

Guardrails:
- Require a local-only token or IP check.
- Add a global kill-switch (`TRADING_ENABLED=false`).

## Data contract (frontend types)
- Candle: {timestamp, open, high, low, close, volume}
- FundingSnapshot: {symbol, timestamp, funding_rate, next_funding_time}
- PriceSnapshot: {symbol, timestamp, last, mark, index}
- Decision: {timestamp, action, confidence, reasoning}
- Order: {order_id, symbol, side, type, status, filled_amount, average_price}
- Trade: {timestamp, symbol, side, price, amount, fee}
- Position: {symbol, side, size, entry_price, unrealized_pnl}

## Milestones checklist
- [ ] API adapter ready (Phase 1)
- [ ] React app runs and shows tables (Phase 2)
- [ ] Core pages done (Phase 3)
- [ ] Refresh + UX polish (Phase 4)
- [ ] Optional controls (Phase 5)
