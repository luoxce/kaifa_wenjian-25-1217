"""Frontend API server (read-only) for Alpha Arena."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.data.health import coverage_summary, scan_integrity, repair_candles
from alpha_arena.execution.okx_executor import OKXOrderExecutor
from alpha_arena.execution.order_tracker import OrderTracker
from alpha_arena.ingest.okx import ingest_all
from alpha_arena.strategies.registry import STRATEGY_SPECS, StrategyLibrary
from alpha_arena.utils.time import utc_now_s

from run_backtest_mvp import (
    BacktestDataService,
    BacktestRecorder,
    SimpleBacktester,
    compute_metrics,
)

try:
    from alpha_arena.rl.rl_integration import RLDecisionMaker  # noqa: F401

    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False


def _parse_db_path(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://") :]
    raise ValueError(f"Unsupported DATABASE_URL: {database_url}")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def _parse_ts(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = int(value)
        return ts * 1000 if ts < 1_000_000_000_000 else ts
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            ts = int(text)
            return ts * 1000 if ts < 1_000_000_000_000 else ts
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    return None


def _risk_value(payload: Optional[dict], *keys: str) -> Optional[float]:
    if not payload:
        return None
    for key in keys:
        if key in payload and payload[key] is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    return None


class ScanRequest(BaseModel):
    symbol: str
    timeframes: list[str]
    range_start_ts: Optional[int] = None
    range_end_ts: Optional[int] = None


class RepairRequest(BaseModel):
    symbol: str
    timeframe: str
    range_start_ts: int
    range_end_ts: int
    mode: str = "refetch"


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    limit: int = 2000
    signal_window: int = 300
    initial_capital: float = 10000.0
    fee_rate: float = 0.0005
    name: Optional[str] = None
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slippage_bps: float = 0.0
    slippage_model: str = "fixed"
    order_size_mode: str = "percentEquity"
    order_size_value: float = 1.0
    allow_short: bool = True
    funding_enabled: bool = True
    leverage: float = 1.0
    risk: Optional[dict] = None
    strategy_params: Optional[dict] = None


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="Alpha Arena API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    data_service = DataService(db_path=db_path)

    def _require_write_enabled() -> None:
        if not settings.api_write_enabled:
            raise HTTPException(status_code=403, detail="API write actions disabled.")

    @app.get("/api/health", response_class=JSONResponse)
    def api_health() -> JSONResponse:
        start = time.time()
        last_sync_time = None
        with _connect(db_path) as conn:
            row = conn.execute(
                "SELECT MAX(timestamp) AS ts FROM balances"
            ).fetchone()
            if row and row["ts"] is not None:
                last_sync_time = int(row["ts"])
        latency_ms = int((time.time() - start) * 1000)
        trading_enabled = settings.trading_enabled
        return JSONResponse(
            {
                "status": "ok",
                "latency_ms": latency_ms,
                "last_sync_time": last_sync_time or int(time.time() * 1000),
                "trading_enabled": trading_enabled,
                "api_write_enabled": settings.api_write_enabled,
                "okx_is_demo": settings.okx_is_demo,
                "okx_td_mode": settings.okx_td_mode,
                "okx_default_symbol": settings.okx_default_symbol,
                "okx_default_market": settings.okx_default_market,
            }
        )

    def _rl_enabled() -> bool:
        return os.getenv("RL_ENABLED", "false").lower() == "true"

    def _rl_last_prediction_ts(conn: sqlite3.Connection) -> Optional[str]:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rl_decisions'"
        ).fetchone()
        if not row:
            return None
        try:
            data = conn.execute(
                "SELECT MAX(timestamp) AS ts FROM rl_decisions"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if not data or data["ts"] is None:
            return None
        ts = _parse_ts(data["ts"])
        if ts is None:
            return None
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()

    @app.get("/api/rl/status", response_class=JSONResponse)
    def api_rl_status() -> JSONResponse:
        if not _rl_enabled() or not RL_AVAILABLE:
            return JSONResponse({"enabled": False})
        model_path = os.getenv("RL_MODEL_PATH", "models/rl/best_model/best_model.zip")
        model_loaded = os.path.exists(model_path)
        with _connect(db_path) as conn:
            last_prediction_time = _rl_last_prediction_ts(conn)
        return JSONResponse(
            {
                "enabled": True,
                "model_path": model_path,
                "model_loaded": model_loaded,
                "last_prediction_time": last_prediction_time,
                "mode": os.getenv("DECISION_MODE", "hybrid"),
            }
        )

    @app.get("/api/rl/stats", response_class=JSONResponse)
    def api_rl_stats() -> JSONResponse:
        if not _rl_enabled() or not RL_AVAILABLE:
            return JSONResponse({"enabled": False})
        payload = {
            "enabled": True,
            "total_decisions": 0,
            "rl_interventions": 0,
            "intervention_rate": 0.0,
            "avg_position": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "last_24h_return": 0.0,
        }
        with _connect(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rl_decisions'"
            ).fetchone()
            if not has_table:
                return JSONResponse(payload)
            try:
                stats = conn.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN rl_adjusted = 1 THEN 1 ELSE 0 END) AS interventions,
                           AVG(rl_position) AS avg_position,
                           AVG(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS win_rate,
                           AVG(sharpe) AS sharpe_ratio
                    FROM rl_decisions
                    """
                ).fetchone()
            except sqlite3.OperationalError:
                return JSONResponse(payload)

            total = stats["total"] or 0
            interventions = stats["interventions"] or 0
            payload.update(
                {
                    "total_decisions": int(total),
                    "rl_interventions": int(interventions),
                    "intervention_rate": float(interventions) / float(total)
                    if total
                    else 0.0,
                    "avg_position": float(stats["avg_position"] or 0.0),
                    "win_rate": float(stats["win_rate"] or 0.0),
                    "sharpe_ratio": float(stats["sharpe_ratio"] or 0.0),
                }
            )
            try:
                since = int(time.time()) - 24 * 60 * 60
                row = conn.execute(
                    """
                    SELECT SUM(return_pct) AS total_return
                    FROM rl_decisions
                    WHERE timestamp >= ?
                    """,
                    (since,),
                ).fetchone()
                payload["last_24h_return"] = float(row["total_return"] or 0.0) / 100.0
            except sqlite3.OperationalError:
                pass
        return JSONResponse(payload)

    @app.get("/api/rl/recent_decisions", response_class=JSONResponse)
    def api_rl_recent_decisions(limit: int = Query(10, ge=1, le=200)) -> JSONResponse:
        if not _rl_enabled() or not RL_AVAILABLE:
            return JSONResponse({"enabled": False})
        with _connect(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rl_decisions'"
            ).fetchone()
            if not has_table:
                return JSONResponse([])
            try:
                rows = conn.execute(
                    """
                    SELECT timestamp,
                           rl_position,
                           rl_weights,
                           traditional_signal,
                           final_signal,
                           rl_adjusted
                    FROM rl_decisions
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.OperationalError:
                return JSONResponse([])
        decisions = []
        for row in rows:
            weights = row["rl_weights"]
            if isinstance(weights, str):
                try:
                    weights = json.loads(weights)
                except json.JSONDecodeError:
                    weights = []
            decisions.append(
                {
                    "timestamp": row["timestamp"],
                    "rl_position": row["rl_position"],
                    "rl_weights": weights,
                    "traditional_signal": row["traditional_signal"],
                    "final_signal": row["final_signal"],
                    "rl_adjusted": bool(row["rl_adjusted"]),
                }
            )
        return JSONResponse(decisions)

    @app.get("/api/market/candles", response_class=JSONResponse)
    def api_market_candles(
        symbol: str,
        timeframe: str,
        limit: int = Query(200, ge=1, le=5000),
    ) -> JSONResponse:
        df = data_service.get_candles(symbol, timeframe, limit=limit)
        rows = []
        if not df.empty:
            for _, row in df.iterrows():
                rows.append(
                    {
                        "time": int(row["timestamp"] // 1000),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    }
                )
        return JSONResponse({"symbol": symbol, "timeframe": timeframe, "data": rows})

    @app.get("/api/market/symbols", response_class=JSONResponse)
    def api_market_symbols() -> JSONResponse:
        symbols = data_service.list_symbols()
        return JSONResponse({"data": symbols})

    @app.get("/api/market/timeframes", response_class=JSONResponse)
    def api_market_timeframes(symbol: str) -> JSONResponse:
        timeframes = data_service.list_timeframes(symbol)
        return JSONResponse({"data": timeframes})

    @app.get("/api/market/funding", response_class=JSONResponse)
    def api_market_funding(symbol: str) -> JSONResponse:
        funding = data_service.get_latest_funding(symbol)
        if not funding:
            return JSONResponse({"data": None})
        return JSONResponse(
            {
                "data": {
                    "symbol": funding.symbol,
                    "timestamp": funding.timestamp,
                    "funding_rate": funding.funding_rate,
                    "next_funding_time": funding.next_funding_time,
                }
            }
        )

    @app.get("/api/market/prices", response_class=JSONResponse)
    def api_market_prices(symbol: str) -> JSONResponse:
        prices = data_service.get_latest_prices(symbol)
        if not prices:
            return JSONResponse({"data": None})
        return JSONResponse(
            {
                "data": {
                    "symbol": prices.symbol,
                    "timestamp": prices.timestamp,
                    "last": prices.last,
                    "mark": prices.mark,
                    "index": prices.index,
                }
            }
        )

    @app.get("/api/decisions", response_class=JSONResponse)
    def api_decisions(
        symbol: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT timestamp, action, confidence, reasoning
                FROM decisions
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        decisions = []
        for row in rows:
            action = row["action"] or ""
            signal = action if action in {"BUY", "SELL", "HOLD"} else "HOLD"
            decisions.append(
                {
                    "timestamp": row["timestamp"],
                    "strategy_name": action,
                    "signal": signal,
                    "confidence": row["confidence"] or 0.0,
                    "reasoning": row["reasoning"] or "",
                }
            )
        return JSONResponse({"data": decisions})

    @app.get("/api/orders", response_class=JSONResponse)
    def api_orders(
        symbol: str,
        limit: int = Query(50, ge=1, le=500),
        status: str = Query("open"),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            columns = _get_columns(conn, "orders")
            filled_col = "filled_amount" if "filled_amount" in columns else None
            timestamp_col = "updated_at" if "updated_at" in columns else "created_at"
            clause = ""
            params = [symbol]
            status_key = (status or "").lower()
            if status_key in {"open", "opened"}:
                clause = "AND status IN ('NEW', 'PARTIALLY_FILLED')"
            elif status_key in {"closed", "history"}:
                clause = "AND status IN ('FILLED', 'CANCELED', 'REJECTED')"
            rows = conn.execute(
                f"""
                SELECT client_order_id AS order_id,
                       symbol,
                       side,
                       status,
                       price,
                       {filled_col or '0'} AS filled_amount,
                       {timestamp_col} AS timestamp
                FROM orders
                WHERE symbol = ?
                {clause}
                ORDER BY {timestamp_col} DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        orders = [dict(row) for row in rows]
        return JSONResponse({"data": orders})

    @app.get("/api/trades", response_class=JSONResponse)
    def api_trades(
        symbol: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            has_trades = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='trades'"
            ).fetchone()
            if not has_trades:
                return JSONResponse({"data": []})
            try:
                rows = conn.execute(
                    """
                    SELECT symbol, side, price, amount, fee, timestamp
                    FROM trades
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (symbol, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return JSONResponse({"data": []})
        trades = [dict(row) for row in rows]
        return JSONResponse({"data": trades})

    @app.get("/api/positions", response_class=JSONResponse)
    def api_positions(symbol: str) -> JSONResponse:
        with _connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT p.symbol,
                       p.side,
                       p.size,
                       p.entry_price,
                       p.unrealized_pnl,
                       ps.mark_price
                FROM positions p
                LEFT JOIN position_snapshots ps
                  ON ps.symbol = p.symbol
                 AND ps.side = p.side
                 AND ps.timestamp = (
                     SELECT MAX(timestamp)
                     FROM position_snapshots ps2
                     WHERE ps2.symbol = p.symbol AND ps2.side = p.side
                 )
                WHERE p.symbol = ?
                ORDER BY p.updated_at DESC
                """,
                (symbol,),
            ).fetchall()
        positions = [dict(row) for row in rows]
        return JSONResponse({"data": positions})

    @app.get("/api/balances", response_class=JSONResponse)
    def api_balances(currency: str = "") -> JSONResponse:
        with _connect(db_path) as conn:
            if currency:
                rows = conn.execute(
                    """
                    SELECT currency, total, free, used, timestamp
                    FROM balances
                    WHERE currency = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (currency,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT b.currency, b.total, b.free, b.used, b.timestamp
                    FROM balances b
                    WHERE b.timestamp = (
                        SELECT MAX(timestamp)
                        FROM balances b2
                        WHERE b2.currency = b.currency
                    )
                    ORDER BY b.currency
                    """,
                ).fetchall()
        balances = [dict(row) for row in rows]
        return JSONResponse({"data": balances})

    @app.get("/api/account/summary", response_class=JSONResponse)
    def api_account_summary() -> JSONResponse:
        with _connect(db_path) as conn:
            balances = conn.execute(
                """
                SELECT b.currency, b.total, b.free, b.used
                FROM balances b
                WHERE b.timestamp = (
                    SELECT MAX(timestamp)
                    FROM balances b2
                    WHERE b2.currency = b.currency
                )
                ORDER BY b.currency
                """
            ).fetchall()
            positions = conn.execute(
                """
                SELECT unrealized_pnl
                FROM positions
                """
            ).fetchall()

        balances_list = [dict(row) for row in balances]
        total_equity = 0.0
        usdt_row = next((b for b in balances_list if b["currency"] == "USDT"), None)
        if usdt_row:
            total_equity = float(usdt_row.get("total") or 0.0)
        else:
            total_equity = sum(float(b.get("total") or 0.0) for b in balances_list)

        unrealized = sum(float(p["unrealized_pnl"] or 0.0) for p in positions)
        return JSONResponse(
            {
                "total_equity": total_equity,
                "unrealized_pnl": unrealized,
                "daily_pnl": 0.0,
                "balances": [
                    {
                        "asset": b["currency"],
                        "free": float(b.get("free") or 0.0),
                        "used": float(b.get("used") or 0.0),
                        "total": float(b.get("total") or 0.0),
                    }
                    for b in balances_list
                ],
            }
        )

    @app.get("/api/backtest/strategies", response_class=JSONResponse)
    def api_backtest_strategies() -> JSONResponse:
        strategies = [
            {
                "key": spec.key,
                "name": spec.name,
                "enabled": spec.enabled,
                "implemented": spec.implemented,
            }
            for spec in STRATEGY_SPECS
            if spec.implemented
        ]
        return JSONResponse({"data": strategies})

    @app.get("/api/backtests", response_class=JSONResponse)
    def api_backtests(limit: int = Query(20, ge=1, le=200)) -> JSONResponse:
        with _connect(db_path) as conn:
            has_runs = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='backtest_runs'"
            ).fetchone()
            if has_runs:
                rows = conn.execute(
                    """
                    SELECT id AS backtest_id,
                           run_id,
                           symbol,
                           timeframe,
                           total_return,
                           max_drawdown,
                           sharpe_ratio,
                           profit_factor,
                           win_rate,
                           final_equity,
                           created_at,
                           metrics_json
                    FROM backtest_runs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT r.id AS backtest_id,
                           c.name,
                           c.symbol,
                           c.timeframe,
                           r.total_return,
                           r.max_drawdown,
                           r.sharpe_ratio,
                           r.profit_factor,
                           r.win_rate,
                           r.final_equity,
                           r.created_at
                    FROM backtest_results r
                    JOIN backtest_configs c ON c.id = r.config_id
                    ORDER BY r.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return JSONResponse({"data": [dict(row) for row in rows]})

    @app.get("/api/backtests/{backtest_id}", response_class=JSONResponse)
    def api_backtest_detail(backtest_id: int) -> JSONResponse:
        with _connect(db_path) as conn:
            has_runs = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='backtest_runs'"
            ).fetchone()
            row = None
            use_runs = False
            if has_runs:
                row = conn.execute(
                    """
                    SELECT *
                    FROM backtest_runs
                    WHERE id = ?
                    """,
                    (backtest_id,),
                ).fetchone()
                if row is not None:
                    use_runs = True

            if row is None:
                row = conn.execute(
                    """
                    SELECT r.*, c.name, c.symbol, c.timeframe, c.initial_capital, c.commission_rate
                    FROM backtest_results r
                    JOIN backtest_configs c ON c.id = r.config_id
                    WHERE r.id = ?
                    """,
                    (backtest_id,),
                ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Backtest not found.")
        payload = dict(row)
        if use_runs:
            with _connect(db_path) as conn:
                legacy = conn.execute(
                    "SELECT trade_log, equity_curve FROM backtest_results WHERE id = ?",
                    (backtest_id,),
                ).fetchone()
            if legacy:
                if legacy["trade_log"] is not None:
                    payload["trade_log"] = legacy["trade_log"]
                if payload.get("equity_curve_json") is None and legacy["equity_curve"] is not None:
                    payload["equity_curve_json"] = legacy["equity_curve"]
        return JSONResponse({"data": payload})

    @app.get("/api/data-health/coverage", response_class=JSONResponse)
    def api_data_health_coverage(symbol: str) -> JSONResponse:
        rows = coverage_summary(symbol)
        return JSONResponse(
            {
                "symbol": symbol,
                "timeframes": [
                    {
                        "timeframe": row.timeframe,
                        "start_ts": row.start_ts,
                        "end_ts": row.end_ts,
                        "bars": row.bars,
                        "expected_bars_estimate": row.expected_bars_estimate,
                        "missing_bars_estimate": row.missing_bars_estimate,
                        "last_updated_at": row.last_updated_at,
                    }
                    for row in rows
                ],
            }
        )

    @app.get("/api/data-health/integrity-events", response_class=JSONResponse)
    def api_data_health_events(
        symbol: str,
        timeframe: str = "",
        limit: int = Query(200, ge=1, le=1000),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            clause = "WHERE symbol = ?"
            params: list = [symbol]
            if timeframe:
                clause += " AND timeframe = ?"
                params.append(timeframe)
            rows = conn.execute(
                f"""
                SELECT *
                FROM candle_integrity_events
                {clause}
                ORDER BY detected_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return JSONResponse({"data": [dict(row) for row in rows]})

    @app.post("/api/data-health/scan", response_class=JSONResponse)
    def api_data_health_scan(payload: ScanRequest = Body(...)) -> JSONResponse:
        _require_write_enabled()
        summary = scan_integrity(
            symbol=payload.symbol,
            timeframes=payload.timeframes,
            range_start_ts=payload.range_start_ts,
            range_end_ts=payload.range_end_ts,
        )
        return JSONResponse({"data": summary})

    @app.post("/api/data-health/repair", response_class=JSONResponse)
    def api_data_health_repair(payload: RepairRequest = Body(...)) -> JSONResponse:
        _require_write_enabled()
        result = repair_candles(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            range_start_ts=payload.range_start_ts,
            range_end_ts=payload.range_end_ts,
            mode=payload.mode,
        )
        return JSONResponse({"data": result})

    @app.get("/api/data-health/repair-jobs", response_class=JSONResponse)
    def api_data_health_repair_jobs(
        symbol: str = "",
        timeframe: str = "",
        limit: int = Query(200, ge=1, le=1000),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            clauses = []
            params: list = []
            if symbol:
                clauses.append("symbol = ?")
                params.append(symbol)
            if timeframe:
                clauses.append("timeframe = ?")
                params.append(timeframe)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"""
                SELECT *
                FROM candle_repair_jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return JSONResponse({"data": [dict(row) for row in rows]})

    @app.post("/api/backtest/run", response_class=JSONResponse)
    def api_backtest_run(payload: BacktestRequest = Body(...)) -> JSONResponse:
        _require_write_enabled()
        service = DataService(db_path=db_path)
        requested_start_ts = _parse_ts(payload.start_ts) or _parse_ts(payload.start_time)
        requested_end_ts = _parse_ts(payload.end_ts) or _parse_ts(payload.end_time)
        limit = payload.limit if payload.limit and payload.limit > 0 else None
        if requested_start_ts or requested_end_ts:
            candles = service.get_candles_range(
                payload.symbol,
                payload.timeframe,
                start_ts=requested_start_ts,
                end_ts=requested_end_ts,
                limit=limit,
            )
        else:
            candles = service.get_ohlcv(payload.symbol, payload.timeframe, limit=payload.limit)
        if candles.empty:
            raise HTTPException(status_code=400, detail="No candles loaded.")

        funding_history = service.get_funding_history(payload.symbol, limit=payload.limit)
        backtest_data = BacktestDataService(candles, funding=funding_history)
        library = StrategyLibrary(backtest_data)
        strategy_params = payload.strategy_params if isinstance(payload.strategy_params, dict) else None
        strategy = library.build(
            payload.strategy,
            payload.symbol,
            payload.timeframe,
            params=strategy_params,
        )
        strategy.data_limit = min(payload.signal_window, len(candles))

        start_ts = int(candles.iloc[0]["timestamp"])
        end_ts = int(candles.iloc[-1]["timestamp"])
        session_name = payload.name or f"{payload.strategy}_{payload.timeframe}_{utc_now_s()}"
        params_payload = {
            "strategy_key": payload.strategy,
            "strategy_params": strategy.params,
            "signal_window": payload.signal_window,
            "execution": {
                "fee_rate": payload.fee_rate,
                "slippage_bps": payload.slippage_bps,
                "slippage_model": payload.slippage_model,
                "order_size_mode": payload.order_size_mode,
                "order_size_value": payload.order_size_value,
                "allow_short": payload.allow_short,
                "funding_enabled": payload.funding_enabled,
                "leverage": payload.leverage,
            },
            "risk": payload.risk or {},
            "range": {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "requested_start_ts": requested_start_ts,
                "requested_end_ts": requested_end_ts,
                "limit": payload.limit,
            },
        }
        recorder = BacktestRecorder(
            name=session_name,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start_ts=start_ts,
            end_ts=end_ts,
            initial_capital=payload.initial_capital,
            fee_rate=payload.fee_rate,
            strategy_payload=params_payload,
        )

        backtester = SimpleBacktester(
            initial_capital=payload.initial_capital,
            fee_rate=payload.fee_rate,
            slippage_bps=payload.slippage_bps,
            slippage_model=payload.slippage_model,
            order_size_mode=payload.order_size_mode,
            order_size_value=payload.order_size_value,
            allow_short=payload.allow_short,
            leverage=payload.leverage,
            max_drawdown=_risk_value(payload.risk, "max_drawdown", "maxDrawdown"),
            max_position=_risk_value(payload.risk, "max_position", "maxPosition"),
        )
        try:
            results = backtester.run(candles, strategy, backtest_data, recorder=recorder)
            metrics = compute_metrics(results, payload.initial_capital)
            recorder.finalize(results, metrics)
        finally:
            recorder.close()

        return JSONResponse(
            {
                "backtest_id": recorder.backtest_id,
                "config_id": recorder.config_id,
                "metrics": metrics,
            }
        )

    class IngestRequest(BaseModel):
        symbol: str
        since_days: int = 30
        timeframes: Optional[List[str]] = None
        max_bars: Optional[int] = None

    class SyncOrdersHistoryRequest(BaseModel):
        symbol: Optional[str] = None
        symbols: Optional[List[str]] = None
        since_days: int = 30
        since_ms: Optional[int] = None
        limit: int = 100
        include_open: bool = True
        include_closed: bool = True
        include_trades: bool = True

    @app.post("/api/actions/ingest", response_class=JSONResponse)
    def api_action_ingest(payload: IngestRequest = Body(...)) -> JSONResponse:
        _require_write_enabled()
        timeframes = payload.timeframes or list(settings.okx_timeframes)
        results = ingest_all(
            symbol=payload.symbol,
            timeframes=timeframes,
            since_days=payload.since_days,
            max_bars=payload.max_bars,
        )
        return JSONResponse({"data": results})

    @app.post("/api/actions/sync_account", response_class=JSONResponse)
    def api_action_sync_account(symbol: str = Body("", embed=True)) -> JSONResponse:
        _require_write_enabled()
        executor = OKXOrderExecutor()
        symbols = [symbol] if symbol else None
        executor.sync_account_state(symbols)
        return JSONResponse({"status": "ok"})

    @app.post("/api/actions/sync_orders", response_class=JSONResponse)
    def api_action_sync_orders() -> JSONResponse:
        _require_write_enabled()
        tracker = OrderTracker()
        updated = tracker.sync_orders(only_open=True)
        return JSONResponse({"status": "ok", "updated": updated})

    @app.post("/api/actions/sync_orders_full", response_class=JSONResponse)
    def api_action_sync_orders_full(
        payload: SyncOrdersHistoryRequest = Body(...)
    ) -> JSONResponse:
        _require_write_enabled()
        tracker = OrderTracker()
        symbols = payload.symbols or ([payload.symbol] if payload.symbol else None)
        since_ms = payload.since_ms
        if since_ms is None and payload.since_days > 0:
            since_ms = int(time.time() * 1000) - payload.since_days * 24 * 60 * 60 * 1000
        result = tracker.sync_exchange_history(
            symbols=symbols,
            since_ms=since_ms,
            limit=payload.limit,
            include_open=payload.include_open,
            include_closed=payload.include_closed,
            include_trades=payload.include_trades,
        )
        return JSONResponse({"status": "ok", "result": result})

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpha Arena API server.")
    parser.add_argument(
        "--db",
        default="",
        help="SQLite path (defaults to DATABASE_URL).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db or _parse_db_path(settings.database_url)
    app = create_app(db_path)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
