CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    exchange TEXT NOT NULL,
    account_id TEXT,
    currency TEXT NOT NULL,
    total NUMERIC NOT NULL,
    available NUMERIC,
    used NUMERIC,
    price_usdt NUMERIC,
    total_usdt NUMERIC,
    available_usdt NUMERIC,
    used_usdt NUMERIC,
    raw_payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_exchange_account_ts
ON balance_snapshots(exchange, account_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_currency_ts
ON balance_snapshots(currency, timestamp DESC);

ALTER TABLE position_snapshots ADD COLUMN exchange TEXT;
ALTER TABLE position_snapshots ADD COLUMN account_id TEXT;
ALTER TABLE position_snapshots ADD COLUMN qty NUMERIC;
ALTER TABLE position_snapshots ADD COLUMN notional_usdt NUMERIC;
ALTER TABLE position_snapshots ADD COLUMN unrealized_pnl_usdt NUMERIC;
ALTER TABLE position_snapshots ADD COLUMN margin_usdt NUMERIC;
ALTER TABLE position_snapshots ADD COLUMN raw_payload TEXT;

CREATE INDEX IF NOT EXISTS idx_position_snapshots_exchange_account_symbol_ts
ON position_snapshots(exchange, account_id, symbol, timestamp DESC);
