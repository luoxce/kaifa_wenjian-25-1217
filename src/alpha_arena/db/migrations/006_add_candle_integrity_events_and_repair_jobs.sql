CREATE TABLE IF NOT EXISTS candle_integrity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    event_type TEXT NOT NULL,
    start_ts INTEGER,
    end_ts INTEGER,
    expected_bars INTEGER,
    actual_bars INTEGER,
    missing_bars INTEGER,
    duplicate_bars INTEGER,
    severity TEXT,
    detected_at INTEGER NOT NULL,
    repair_job_id TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_candle_integrity_events_symbol_timeframe_detected
ON candle_integrity_events(symbol, timeframe, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_candle_integrity_events_symbol_timeframe_start
ON candle_integrity_events(symbol, timeframe, start_ts DESC);

CREATE TABLE IF NOT EXISTS candle_repair_jobs (
    job_id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    range_start_ts INTEGER NOT NULL,
    range_end_ts INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    repaired_bars INTEGER,
    raw_payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_candle_repair_jobs_symbol_timeframe_created
ON candle_repair_jobs(symbol, timeframe, created_at DESC);
