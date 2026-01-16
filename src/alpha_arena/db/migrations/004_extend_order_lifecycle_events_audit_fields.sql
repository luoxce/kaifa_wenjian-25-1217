ALTER TABLE order_lifecycle_events ADD COLUMN exchange TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN symbol TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN exchange_status TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN exchange_event_ts INTEGER;
ALTER TABLE order_lifecycle_events ADD COLUMN raw_payload TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN client_order_id TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN trade_id TEXT;
ALTER TABLE order_lifecycle_events ADD COLUMN fill_qty NUMERIC;
ALTER TABLE order_lifecycle_events ADD COLUMN fill_price NUMERIC;
ALTER TABLE order_lifecycle_events ADD COLUMN fee NUMERIC;
ALTER TABLE order_lifecycle_events ADD COLUMN fee_currency TEXT;

CREATE INDEX IF NOT EXISTS idx_order_lifecycle_events_exchange_order_ts
ON order_lifecycle_events(exchange, order_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_order_lifecycle_events_symbol_ts
ON order_lifecycle_events(symbol, timestamp DESC);
