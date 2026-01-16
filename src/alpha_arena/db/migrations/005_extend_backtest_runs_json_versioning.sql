CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    created_at INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    initial_capital NUMERIC NOT NULL,
    params_json TEXT,
    metrics_json TEXT,
    equity_curve_json TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1,
    artifacts_path TEXT,
    total_return NUMERIC,
    max_drawdown NUMERIC,
    win_rate NUMERIC,
    profit_factor NUMERIC,
    sharpe_ratio NUMERIC,
    final_equity NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol_timeframe_created_at
ON backtest_runs(symbol, timeframe, created_at DESC);
