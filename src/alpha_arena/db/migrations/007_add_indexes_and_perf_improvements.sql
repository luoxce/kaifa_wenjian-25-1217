CREATE INDEX IF NOT EXISTS idx_orders_client_order_id
ON orders(client_order_id);

CREATE INDEX IF NOT EXISTS idx_orders_exchange_order_id
ON orders(exchange_order_id);

CREATE INDEX IF NOT EXISTS idx_orders_status
ON orders(status);

CREATE INDEX IF NOT EXISTS idx_trades_order_id
ON trades(order_id);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_timestamp_asc
ON market_data(symbol, timeframe, timestamp ASC);

CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at
ON backtest_results(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_configs_symbol_timeframe
ON backtest_configs(symbol, timeframe);
