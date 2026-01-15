"""Frontend API server (read-only) for Alpha Arena."""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path
import sys
from typing import List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService
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
            }
        )

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
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            columns = _get_columns(conn, "orders")
            filled_col = "filled_amount" if "filled_amount" in columns else None
            timestamp_col = "updated_at" if "updated_at" in columns else "created_at"
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
                ORDER BY {timestamp_col} DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        orders = [dict(row) for row in rows]
        return JSONResponse({"data": orders})

    @app.get("/api/trades", response_class=JSONResponse)
    def api_trades(
        symbol: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
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
        return JSONResponse({"data": payload})

    class BacktestRequest(BaseModel):
        symbol: str
        timeframe: str
        strategy: str
        limit: int = 2000
        signal_window: int = 300
        initial_capital: float = 10000.0
        fee_rate: float = 0.0005
        name: Optional[str] = None

    @app.post("/api/backtest/run", response_class=JSONResponse)
    def api_backtest_run(payload: BacktestRequest = Body(...)) -> JSONResponse:
        _require_write_enabled()
        service = DataService(db_path=db_path)
        candles = service.get_ohlcv(payload.symbol, payload.timeframe, limit=payload.limit)
        if candles.empty:
            raise HTTPException(status_code=400, detail="No candles loaded.")

        funding_history = service.get_funding_history(payload.symbol, limit=payload.limit)
        backtest_data = BacktestDataService(candles, funding=funding_history)
        library = StrategyLibrary(backtest_data)
        strategy = library.build(payload.strategy, payload.symbol, payload.timeframe, params=None)
        strategy.data_limit = min(payload.signal_window, len(candles))

        start_ts = int(candles.iloc[0]["timestamp"])
        end_ts = int(candles.iloc[-1]["timestamp"])
        session_name = payload.name or f"{payload.strategy}_{payload.timeframe}_{utc_now_s()}"
        recorder = BacktestRecorder(
            name=session_name,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start_ts=start_ts,
            end_ts=end_ts,
            initial_capital=payload.initial_capital,
            fee_rate=payload.fee_rate,
            strategy_payload={
                "strategy_key": payload.strategy,
                "strategy_params": strategy.params,
                "signal_window": payload.signal_window,
            },
        )

        backtester = SimpleBacktester(
            initial_capital=payload.initial_capital, fee_rate=payload.fee_rate
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
