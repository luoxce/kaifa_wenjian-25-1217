CREATE TABLE IF NOT EXISTS prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    metadata TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS llm_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER,
    model_version_id INTEGER,
    timestamp INTEGER NOT NULL,
    request TEXT,
    response TEXT,
    status TEXT,
    latency_ms INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id)
);

CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_timestamp
ON market_data(symbol, timeframe, timestamp DESC);

CREATE TABLE IF NOT EXISTS funding_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    funding_rate NUMERIC NOT NULL,
    next_funding_time INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_funding_rates_symbol_timestamp
ON funding_rates(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    last_price NUMERIC,
    mark_price NUMERIC,
    index_price NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_price_snapshots_symbol_timestamp
ON price_snapshots(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open_interest NUMERIC NOT NULL,
    open_interest_value NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_open_interest_symbol_timestamp
ON open_interest(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS long_short_ratio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    ratio NUMERIC NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_long_short_ratio_symbol_timestamp
ON long_short_ratio(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    total NUMERIC NOT NULL,
    free NUMERIC,
    used NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(currency, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_balances_currency_timestamp
ON balances(currency, timestamp DESC);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    action TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    technical_analysis TEXT,
    risk_assessment TEXT,
    llm_response TEXT,
    llm_run_id INTEGER,
    prompt_version_id INTEGER,
    model_version_id INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (llm_run_id) REFERENCES llm_runs(id),
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_decisions_symbol_timestamp
ON decisions(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    price NUMERIC,
    amount NUMERIC NOT NULL,
    leverage NUMERIC,
    status TEXT NOT NULL,
    client_order_id TEXT,
    exchange_order_id TEXT,
    time_in_force TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol_created_at
ON orders(symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS order_lifecycle_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_order_lifecycle_events_order_id
ON order_lifecycle_events(order_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price NUMERIC NOT NULL,
    amount NUMERIC NOT NULL,
    fee NUMERIC,
    fee_currency TEXT,
    realized_pnl NUMERIC,
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp
ON trades(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    size NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    leverage NUMERIC,
    unrealized_pnl NUMERIC,
    margin NUMERIC,
    liquidation_price NUMERIC,
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_positions_symbol_updated_at
ON positions(symbol, updated_at DESC);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,
    size NUMERIC NOT NULL,
    entry_price NUMERIC,
    mark_price NUMERIC,
    unrealized_pnl NUMERIC,
    leverage NUMERIC,
    margin NUMERIC,
    liquidation_price NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp, side)
);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_symbol_timestamp
ON position_snapshots(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    level TEXT NOT NULL,
    rule TEXT NOT NULL,
    details TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_risk_events_symbol_timestamp
ON risk_events(symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    data_type TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    rows_inserted INTEGER,
    status TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_symbol_started_at
ON ingestion_runs(symbol, started_at DESC);

CREATE TABLE IF NOT EXISTS backtest_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    initial_capital NUMERIC NOT NULL,
    commission_rate NUMERIC NOT NULL,
    strategy_params TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    total_return NUMERIC,
    max_drawdown NUMERIC,
    sharpe_ratio NUMERIC,
    profit_factor NUMERIC,
    total_trades INTEGER,
    profitable_trades INTEGER,
    win_rate NUMERIC,
    final_equity NUMERIC,
    equity_curve TEXT,
    trade_log TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (config_id) REFERENCES backtest_configs(id)
);

CREATE TABLE IF NOT EXISTS backtest_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,
    price NUMERIC NOT NULL,
    amount NUMERIC NOT NULL,
    fee NUMERIC NOT NULL,
    pnl NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);

CREATE TABLE IF NOT EXISTS backtest_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    unrealized_pnl NUMERIC,
    stop_loss NUMERIC,
    take_profit NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);

CREATE TABLE IF NOT EXISTS backtest_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    action TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);
