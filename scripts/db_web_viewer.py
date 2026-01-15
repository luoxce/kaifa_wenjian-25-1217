"""Minimal read-only web viewer for the SQLite database."""

from __future__ import annotations

import argparse
import html
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService


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


def _list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def _get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
    return int(row["cnt"]) if row else 0


def _order_by_column(columns: List[str]) -> str:
    if "timestamp" in columns:
        return "timestamp"
    if "created_at" in columns:
        return "created_at"
    return "rowid"


def _fetch_rows(
    conn: sqlite3.Connection, table: str, limit: int, offset: int
) -> Tuple[List[str], List[sqlite3.Row], int]:
    columns = _get_columns(conn, table)
    order_by = _order_by_column(columns)
    rows = conn.execute(
        f"SELECT * FROM {table} ORDER BY {order_by} DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    count = _table_count(conn, table)
    return columns, rows, count


def _html_table(columns: List[str], rows: List[sqlite3.Row]) -> str:
    header_cells = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row[col])) if row[col] is not None else ''}</td>"
            for col in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "\n".join(body_rows) if body_rows else "<tr><td colspan='999'>No data.</td></tr>"
    return f"""
    <table>
      <thead><tr>{header_cells}</tr></thead>
      <tbody>
        {body_html}
      </tbody>
    </table>
    """


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="Alpha Arena DB Viewer")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    data_service = DataService(db_path=db_path)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        with _connect(db_path) as conn:
            tables = _list_tables(conn)
            table_rows = []
            for table in tables:
                count = _table_count(conn, table)
                table_rows.append(
                    f"<li><a href='/table/{table}'>{html.escape(table)}</a> "
                    f"(rows: {count})</li>"
                )
        return f"""
        <html>
          <head>
            <title>Alpha Arena DB Viewer</title>
            <style>
              body {{ font-family: Arial, sans-serif; margin: 24px; }}
              table {{ border-collapse: collapse; width: 100%; }}
              th, td {{ border: 1px solid #ddd; padding: 6px 8px; }}
              th {{ background: #f2f2f2; text-align: left; }}
              .meta {{ color: #666; font-size: 0.9em; }}
            </style>
          </head>
          <body>
            <h1>Alpha Arena DB Viewer</h1>
            <div class="meta">DB path: {html.escape(db_path)}</div>
            <h2>Tables</h2>
            <ul>
              {''.join(table_rows)}
            </ul>
            <p class="meta">Tip: add ?limit=50&offset=0 on table pages.</p>
          </body>
        </html>
        """

    @app.get("/table/{table}", response_class=HTMLResponse)
    def table_view(
        table: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> str:
        with _connect(db_path) as conn:
            tables = _list_tables(conn)
            if table not in tables:
                raise HTTPException(status_code=404, detail=f"Table not found: {table}")
            columns, rows, count = _fetch_rows(conn, table, limit, offset)

        table_html = _html_table(columns, rows)
        next_offset = offset + limit
        prev_offset = max(0, offset - limit)
        return f"""
        <html>
          <head>
            <title>Table {html.escape(table)}</title>
            <style>
              body {{ font-family: Arial, sans-serif; margin: 24px; }}
              table {{ border-collapse: collapse; width: 100%; }}
              th, td {{ border: 1px solid #ddd; padding: 6px 8px; }}
              th {{ background: #f2f2f2; text-align: left; }}
              .meta {{ color: #666; font-size: 0.9em; }}
              a {{ text-decoration: none; color: #1a73e8; }}
            </style>
          </head>
          <body>
            <h1>{html.escape(table)}</h1>
            <div class="meta">Rows: {count} | Limit: {limit} | Offset: {offset}</div>
            <div class="meta">
              <a href="/">Back to tables</a> |
              <a href="/table/{html.escape(table)}?limit={limit}&offset={prev_offset}">Prev</a> |
              <a href="/table/{html.escape(table)}?limit={limit}&offset={next_offset}">Next</a>
            </div>
            {table_html}
          </body>
        </html>
        """

    @app.get("/api/tables", response_class=JSONResponse)
    def api_tables() -> JSONResponse:
        with _connect(db_path) as conn:
            tables = _list_tables(conn)
        return JSONResponse({"tables": tables})

    @app.get("/api/table/{table}", response_class=JSONResponse)
    def api_table(
        table: str,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> JSONResponse:
        with _connect(db_path) as conn:
            tables = _list_tables(conn)
            if table not in tables:
                raise HTTPException(status_code=404, detail=f"Table not found: {table}")
            columns, rows, count = _fetch_rows(conn, table, limit, offset)
        payload = [dict(row) for row in rows]
        return JSONResponse({"table": table, "columns": columns, "rows": payload, "count": count})

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
        return JSONResponse(
            {
                "status": "ok",
                "latency_ms": latency_ms,
                "last_sync_time": last_sync_time or int(time.time() * 1000),
                "trading_enabled": True,
            }
        )

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpha Arena DB web viewer.")
    parser.add_argument(
        "--db",
        default="",
        help="SQLite path (defaults to DATABASE_URL).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8001, help="Bind port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db or _parse_db_path(settings.database_url)
    app = create_app(db_path)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
