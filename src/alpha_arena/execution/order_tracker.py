"""Order tracking and lifecycle updates for live orders."""

from __future__ import annotations

import json
import logging
import time
from typing import Iterable, Optional

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.execution.lifecycle import OrderLifecycleManager
from alpha_arena.ingest.okx import create_okx_client
from alpha_arena.models.enums import OrderStatus
from alpha_arena.utils.time import utc_now_ms, utc_now_s


logger = logging.getLogger(__name__)


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_ms(value: object) -> Optional[int]:
    ts = _safe_int(value)
    if ts is None:
        return None
    return ts * 1000 if ts < 1_000_000_000_000 else ts


def _to_s(value: object) -> Optional[int]:
    ts = _to_ms(value)
    return int(ts / 1000) if ts is not None else None


def _normalize_side(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"BUY", "SELL"}:
        return text
    if text == "B":
        return "BUY"
    if text == "S":
        return "SELL"
    return None


def _normalize_order_type(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if "market" in text:
        return "MARKET"
    if "limit" in text or text in {"post_only", "post"}:
        return "LIMIT"
    return None


def _normalize_status(value: object, filled: Optional[float], amount: Optional[float]) -> str:
    text = str(value or "").strip().lower()
    if text in {"canceled", "cancelled"}:
        return OrderStatus.CANCELED.value
    if text in {"rejected"}:
        return OrderStatus.REJECTED.value
    if text in {"closed", "filled"}:
        return OrderStatus.FILLED.value
    if text in {"open", "live"}:
        if filled is not None and amount is not None and amount > 0:
            if filled >= amount:
                return OrderStatus.FILLED.value
            if filled > 0:
                return OrderStatus.PARTIALLY_FILLED.value
        return OrderStatus.NEW.value
    if filled is not None and amount is not None and amount > 0:
        if filled >= amount:
            return OrderStatus.FILLED.value
        if filled > 0:
            return OrderStatus.PARTIALLY_FILLED.value
    return OrderStatus.NEW.value


class OrderTracker:
    """Fetch order status from exchange and persist lifecycle updates."""

    def __init__(self, exchange=None, lifecycle_manager: Optional[OrderLifecycleManager] = None) -> None:
        self.exchange = exchange or create_okx_client()
        self.exchange.load_markets()
        self.lifecycle_manager = lifecycle_manager or OrderLifecycleManager()
        self._order_columns = self._load_order_columns()

    def sync_orders(
        self,
        order_ids: Optional[Iterable[str]] = None,
        only_open: bool = True,
    ) -> int:
        """Refresh orders by client_order_id. Returns number of updated orders."""
        orders = self._load_orders(order_ids, only_open=only_open)
        updated = 0
        for row in orders:
            exchange_id = row.get("exchange_order_id")
            if not exchange_id:
                continue
            try:
                response = self.exchange.fetch_order(exchange_id, row["symbol"])
            except Exception as exc:
                logger.warning("fetch_order failed for %s: %s", exchange_id, exc)
                continue

            if self._apply_order_update(row, response):
                updated += 1
        return updated

    def sync_exchange_history(
        self,
        symbols: Optional[Iterable[str]] = None,
        since_ms: Optional[int] = None,
        limit: int = 100,
        include_open: bool = True,
        include_closed: bool = True,
        include_trades: bool = True,
    ) -> dict:
        symbol_list = self._normalize_symbols(symbols)
        results = {
            "orders_inserted": 0,
            "orders_updated": 0,
            "trades_inserted": 0,
            "symbols": {},
        }
        if not symbol_list:
            return results

        with get_connection() as conn:
            for symbol in symbol_list:
                stats = {
                    "orders_inserted": 0,
                    "orders_updated": 0,
                    "trades_inserted": 0,
                }
                orders: list[dict] = []
                if include_open:
                    orders.extend(
                        self._fetch_exchange_orders(symbol, since_ms, limit, closed=False)
                    )
                if include_closed:
                    orders.extend(
                        self._fetch_exchange_orders(symbol, since_ms, limit, closed=True)
                    )

                seen_orders: set[str] = set()
                for order in orders:
                    order_key = self._order_key(order)
                    if order_key:
                        if order_key in seen_orders:
                            continue
                        seen_orders.add(order_key)
                    order_row_id, inserted, updated = self._upsert_exchange_order(
                        conn, order
                    )
                    if order_row_id is None:
                        continue
                    if inserted:
                        stats["orders_inserted"] += 1
                    elif updated:
                        stats["orders_updated"] += 1

                if include_trades:
                    trades = self._fetch_exchange_trades(symbol, since_ms, limit)
                    seen_trades: set[str] = set()
                    for trade in trades:
                        trade_id = (
                            trade.get("id")
                            or trade.get("tradeId")
                            or trade.get("info", {}).get("tradeId")
                            or trade.get("info", {}).get("id")
                        )
                        if trade_id:
                            trade_id = str(trade_id)
                            if trade_id in seen_trades:
                                continue
                            seen_trades.add(trade_id)
                        if self._insert_exchange_trade(conn, trade):
                            stats["trades_inserted"] += 1

                conn.commit()
                results["symbols"][symbol] = stats

        results["orders_inserted"] = sum(
            stat["orders_inserted"] for stat in results["symbols"].values()
        )
        results["orders_updated"] = sum(
            stat["orders_updated"] for stat in results["symbols"].values()
        )
        results["trades_inserted"] = sum(
            stat["trades_inserted"] for stat in results["symbols"].values()
        )
        return results

    def _normalize_symbols(self, symbols: Optional[Iterable[str]]) -> list[str]:
        if symbols:
            return [s.strip() for s in symbols if s and s.strip()]
        if settings.okx_default_symbol:
            return [settings.okx_default_symbol]
        return []

    def _fetch_exchange_orders(
        self,
        symbol: str,
        since_ms: Optional[int],
        limit: int,
        *,
        closed: bool,
    ) -> list[dict]:
        if closed:
            if self.exchange.has.get("fetchClosedOrders"):
                fetch_fn = lambda since: self.exchange.fetch_closed_orders(
                    symbol, since=since, limit=limit
                )
            elif self.exchange.has.get("fetchOrders"):
                fetch_fn = lambda since: self.exchange.fetch_orders(
                    symbol, since=since, limit=limit
                )
            else:
                return []
        else:
            if self.exchange.has.get("fetchOpenOrders"):
                fetch_fn = lambda since: self.exchange.fetch_open_orders(
                    symbol, since=since, limit=limit
                )
            elif self.exchange.has.get("fetchOrders"):
                fetch_fn = lambda since: self.exchange.fetch_orders(
                    symbol, since=since, limit=limit
                )
            else:
                return []
        return self._fetch_paged(fetch_fn, since_ms, limit)

    def _fetch_exchange_trades(
        self,
        symbol: str,
        since_ms: Optional[int],
        limit: int,
    ) -> list[dict]:
        if not self.exchange.has.get("fetchMyTrades"):
            return []
        fetch_fn = lambda since: self.exchange.fetch_my_trades(
            symbol, since=since, limit=limit
        )
        return self._fetch_paged(fetch_fn, since_ms, limit)

    def _fetch_paged(
        self,
        fetch_fn,
        since_ms: Optional[int],
        limit: int,
    ) -> list[dict]:
        if since_ms is None:
            try:
                return fetch_fn(None)
            except TypeError:
                return fetch_fn()
        results: list[dict] = []
        next_since = since_ms
        last_max = None
        for _ in range(200):
            batch = fetch_fn(next_since)
            if not batch:
                break
            results.extend(batch)
            timestamps = [
                ts for ts in (self._extract_ts_ms(item) for item in batch) if ts
            ]
            if not timestamps:
                break
            max_ts = max(timestamps)
            if last_max is not None and max_ts <= last_max:
                break
            last_max = max_ts
            if len(batch) < limit:
                break
            next_since = max_ts + 1
            rate_limit = getattr(self.exchange, "rateLimit", None)
            if rate_limit:
                time.sleep(rate_limit / 1000.0)
        return results

    def _extract_ts_ms(self, payload: dict) -> Optional[int]:
        ts = _to_ms(payload.get("timestamp"))
        if ts is not None:
            return ts
        ts = _to_ms(payload.get("lastTradeTimestamp"))
        if ts is not None:
            return ts
        ts = _to_ms(payload.get("lastUpdateTimestamp"))
        if ts is not None:
            return ts
        info = payload.get("info") or {}
        for key in ("ts", "cTime", "uTime", "fillTime"):
            ts = _to_ms(info.get(key))
            if ts is not None:
                return ts
        dt = payload.get("datetime")
        if dt and hasattr(self.exchange, "parse8601"):
            parsed = self.exchange.parse8601(dt)
            if parsed:
                return _to_ms(parsed)
        return None

    def _order_key(self, order: dict) -> str:
        exchange_id = order.get("id") or order.get("orderId")
        if not exchange_id:
            exchange_id = (order.get("info") or {}).get("ordId")
        if exchange_id:
            return f"ex:{exchange_id}"
        client_id = order.get("clientOrderId") or order.get("client_order_id")
        if not client_id:
            client_id = (order.get("info") or {}).get("clOrdId")
        return f"cl:{client_id}" if client_id else ""

    def _upsert_exchange_order(
        self, conn, order: dict
    ) -> tuple[Optional[int], bool, bool]:
        info = order.get("info") or {}
        exchange_id = order.get("id") or order.get("orderId") or info.get("ordId")
        client_id = (
            order.get("clientOrderId")
            or order.get("client_order_id")
            or info.get("clOrdId")
        )
        symbol = order.get("symbol") or info.get("instId")
        side = _normalize_side(order.get("side") or info.get("side"))
        order_type = _normalize_order_type(order.get("type") or info.get("ordType"))
        amount = _safe_float(
            order.get("amount") or info.get("sz") or order.get("filled") or info.get("accFillSz")
        )
        filled = _safe_float(order.get("filled") or info.get("accFillSz"))
        price = _safe_float(
            order.get("price")
            or order.get("average")
            or info.get("avgPx")
            or info.get("px")
        )
        leverage = _safe_float(order.get("leverage") or info.get("lever"))
        time_in_force = order.get("timeInForce") or info.get("tif")
        status = _normalize_status(order.get("status") or info.get("state"), filled, amount)
        created_at = _to_s(
            order.get("timestamp") or info.get("cTime") or info.get("createdAt")
        )
        updated_at = _to_s(
            order.get("lastUpdateTimestamp")
            or info.get("uTime")
            or order.get("timestamp")
            or info.get("cTime")
        )

        if not symbol or not (exchange_id or client_id):
            return None, False, False
        if client_id is None:
            client_id = exchange_id
        if order_type is None:
            order_type = "MARKET" if price is None else "LIMIT"

        row = None
        if exchange_id:
            row = conn.execute(
                "SELECT id FROM orders WHERE exchange_order_id = ? LIMIT 1",
                (str(exchange_id),),
            ).fetchone()
        if row is None and client_id:
            row = conn.execute(
                "SELECT id FROM orders WHERE client_order_id = ? LIMIT 1",
                (str(client_id),),
            ).fetchone()

        if row:
            conn.execute(
                """
                UPDATE orders
                SET symbol = COALESCE(?, symbol),
                    side = COALESCE(?, side),
                    type = COALESCE(?, type),
                    price = COALESCE(?, price),
                    amount = COALESCE(?, amount),
                    leverage = COALESCE(?, leverage),
                    status = ?,
                    client_order_id = COALESCE(?, client_order_id),
                    exchange_order_id = COALESCE(?, exchange_order_id),
                    time_in_force = COALESCE(?, time_in_force),
                    updated_at = COALESCE(?, updated_at)
                WHERE id = ?
                """,
                (
                    symbol,
                    side,
                    order_type,
                    price,
                    amount,
                    leverage,
                    status,
                    str(client_id) if client_id else None,
                    str(exchange_id) if exchange_id else None,
                    time_in_force,
                    updated_at,
                    row["id"],
                ),
            )
            return int(row["id"]), False, True

        if side is None or order_type is None or amount is None:
            return None, False, False

        cur = conn.execute(
            """
            INSERT INTO orders (
                symbol,
                side,
                type,
                price,
                amount,
                leverage,
                status,
                client_order_id,
                exchange_order_id,
                time_in_force,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                side,
                order_type,
                price,
                amount,
                leverage,
                status,
                str(client_id) if client_id else None,
                str(exchange_id) if exchange_id else None,
                time_in_force,
                created_at or utc_now_s(),
                updated_at or utc_now_s(),
            ),
        )
        return int(cur.lastrowid), True, False

    def _insert_exchange_trade(self, conn, trade: dict) -> bool:
        info = trade.get("info") or {}
        exchange_order_id = trade.get("order") or trade.get("orderId") or info.get("ordId")
        if not exchange_order_id:
            return False
        symbol = trade.get("symbol") or info.get("instId")
        side = _normalize_side(trade.get("side") or info.get("side"))
        price = _safe_float(trade.get("price") or info.get("px"))
        amount = _safe_float(trade.get("amount") or info.get("sz"))
        fee_info = trade.get("fee") or {}
        fee_cost = _safe_float(fee_info.get("cost") or info.get("fee"))
        fee_ccy = fee_info.get("currency") or info.get("feeCcy")
        realized_pnl = _safe_float(info.get("realizedPnl") or info.get("pnl"))
        timestamp = _to_ms(trade.get("timestamp") or info.get("ts"))
        if timestamp is None and trade.get("datetime") and hasattr(self.exchange, "parse8601"):
            parsed = self.exchange.parse8601(trade.get("datetime"))
            timestamp = _to_ms(parsed)

        if not symbol or side is None or price is None or amount is None or timestamp is None:
            return False

        order_row_id = self._ensure_order_row_for_trade(
            conn,
            exchange_order_id=str(exchange_order_id),
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            timestamp_ms=timestamp,
        )
        if order_row_id is None:
            return False

        if self._trade_exists(conn, order_row_id, timestamp, price, amount, side):
            return False

        conn.execute(
            """
            INSERT INTO trades (
                order_id,
                symbol,
                side,
                price,
                amount,
                fee,
                fee_currency,
                realized_pnl,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_row_id,
                symbol,
                side,
                price,
                amount,
                fee_cost,
                fee_ccy,
                realized_pnl,
                int(timestamp),
            ),
        )
        return True

    def _ensure_order_row_for_trade(
        self,
        conn,
        *,
        exchange_order_id: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        timestamp_ms: int,
    ) -> Optional[int]:
        row = conn.execute(
            "SELECT id FROM orders WHERE exchange_order_id = ? LIMIT 1",
            (exchange_order_id,),
        ).fetchone()
        if row:
            return int(row["id"])
        created_at = _to_s(timestamp_ms) or utc_now_s()
        cur = conn.execute(
            """
            INSERT INTO orders (
                symbol,
                side,
                type,
                price,
                amount,
                leverage,
                status,
                client_order_id,
                exchange_order_id,
                time_in_force,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                side,
                "MARKET" if price is None else "LIMIT",
                price,
                amount,
                None,
                OrderStatus.FILLED.value,
                exchange_order_id,
                exchange_order_id,
                None,
                created_at,
                created_at,
            ),
        )
        return int(cur.lastrowid)

    def _trade_exists(
        self,
        conn,
        order_row_id: int,
        timestamp_ms: int,
        price: float,
        amount: float,
        side: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM trades
            WHERE order_id = ?
              AND timestamp = ?
              AND price = ?
              AND amount = ?
              AND side = ?
            LIMIT 1
            """,
            (order_row_id, int(timestamp_ms), float(price), float(amount), side),
        ).fetchone()
        return row is not None

    def _load_order_columns(self) -> set[str]:
        with get_connection() as conn:
            rows = conn.execute("PRAGMA table_info(orders)").fetchall()
        return {row["name"] for row in rows}

    def _load_orders(
        self,
        order_ids: Optional[Iterable[str]],
        only_open: bool,
    ) -> list[dict]:
        select_cols = [
            "id",
            "client_order_id",
            "exchange_order_id",
            "symbol",
            "side",
            "status",
            "amount",
            "price",
        ]
        if "filled_amount" in self._order_columns:
            select_cols.append("filled_amount")
        else:
            select_cols.append("NULL AS filled_amount")
        if "remaining_amount" in self._order_columns:
            select_cols.append("remaining_amount")
        else:
            select_cols.append("NULL AS remaining_amount")
        if "average_price" in self._order_columns:
            select_cols.append("average_price")
        else:
            select_cols.append("NULL AS average_price")
        select_sql = ", ".join(select_cols)
        with get_connection() as conn:
            if order_ids:
                placeholders = ",".join("?" for _ in order_ids)
                rows = conn.execute(
                    f"""
                    SELECT {select_sql}
                    FROM orders
                    WHERE client_order_id IN ({placeholders})
                    """,
                    tuple(order_ids),
                ).fetchall()
            else:
                clause = ""
                params: tuple = ()
                if only_open:
                    clause = "WHERE status IN ('NEW', 'PARTIALLY_FILLED')"
                rows = conn.execute(
                    f"""
                    SELECT {select_sql}
                    FROM orders
                    {clause}
                    """,
                    params,
                ).fetchall()
        return [dict(row) for row in rows]

    def _apply_order_update(self, row: dict, response: dict) -> bool:
        amount = response.get("amount") or row.get("amount") or 0.0
        filled = response.get("filled")
        if filled is None:
            filled = response.get("filledAmount") or 0.0
        remaining = response.get("remaining")
        if remaining is None and amount:
            remaining = max(float(amount) - float(filled), 0.0)
        average_price = response.get("average") or response.get("avgPrice") or response.get("price")

        new_status = self._map_status(response, amount)
        old_status = row.get("status") or ""
        old_filled = row.get("filled_amount") or 0.0

        if filled is not None and float(filled) > float(old_filled) and new_status in {
            OrderStatus.NEW,
            OrderStatus.PARTIALLY_FILLED,
        }:
            self._record_event(
                row["client_order_id"],
                old_status,
                new_status.value,
                f"PARTIAL_FILL filled={filled}",
                symbol=row.get("symbol"),
                response=response,
                fill_qty=float(filled),
                fill_price=_safe_float(average_price),
            )

        status_changed = new_status.value != old_status
        if status_changed:
            event = self._event_name(new_status)
            self._record_event(
                row["client_order_id"],
                old_status,
                new_status.value,
                event,
                symbol=row.get("symbol"),
                response=response,
                fill_qty=_safe_float(filled),
                fill_price=_safe_float(average_price),
            )

        if status_changed or filled is not None:
            self._update_order_row(
                row_id=row["id"],
                status=new_status.value,
                filled=filled,
                remaining=remaining,
                average_price=average_price,
            )

        if new_status == OrderStatus.FILLED:
            self._persist_trade(row, response, filled, average_price)

        return status_changed

    def _update_order_row(
        self,
        row_id: int,
        status: str,
        filled: Optional[float],
        remaining: Optional[float],
        average_price: Optional[float],
    ) -> None:
        updates = ["status = ?", "updated_at = ?"]
        values: list = [status, utc_now_s()]

        if "filled_amount" in self._order_columns:
            updates.append("filled_amount = ?")
            values.append(None if filled is None else float(filled))
        if "remaining_amount" in self._order_columns:
            updates.append("remaining_amount = ?")
            values.append(None if remaining is None else float(remaining))
        if "average_price" in self._order_columns:
            updates.append("average_price = ?")
            values.append(None if average_price is None else float(average_price))

        values.append(row_id)
        sql = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
        with get_connection() as conn:
            conn.execute(sql, tuple(values))
            conn.commit()

    def _map_status(self, response: dict, amount: float) -> OrderStatus:
        status = (response.get("status") or "").lower()
        filled = response.get("filled") or 0.0
        if status in {"canceled", "cancelled"}:
            return OrderStatus.CANCELED
        if status in {"rejected"}:
            return OrderStatus.REJECTED
        if amount and filled:
            if float(filled) >= float(amount):
                return OrderStatus.FILLED
            return OrderStatus.PARTIALLY_FILLED
        if status in {"closed", "filled"}:
            return OrderStatus.FILLED
        return OrderStatus.NEW

    def _event_name(self, status: OrderStatus) -> str:
        if status == OrderStatus.NEW:
            return "ORDER_SUBMITTED"
        if status == OrderStatus.PARTIALLY_FILLED:
            return "PARTIAL_FILL"
        if status == OrderStatus.FILLED:
            return "ORDER_FILLED"
        if status == OrderStatus.CANCELED:
            return "ORDER_CANCELED"
        if status == OrderStatus.REJECTED:
            return "ORDER_REJECTED"
        return "ORDER_UPDATE"

    def _record_event(
        self,
        order_id: str,
        from_status: str,
        to_status: str,
        message: str,
        *,
        symbol: Optional[str] = None,
        response: Optional[dict] = None,
        fill_qty: Optional[float] = None,
        fill_price: Optional[float] = None,
    ) -> None:
        try:
            from_enum = OrderStatus(from_status) if from_status else None
        except Exception:
            from_enum = None
        to_enum = OrderStatus(to_status)
        payload = json.dumps(response, ensure_ascii=True) if response is not None else None
        exchange_status = None
        exchange_ts = None
        trade_id = None
        fee = None
        fee_currency = None
        if response:
            exchange_status = response.get("status")
            exchange_ts = response.get("timestamp")
            trade_id = response.get("tradeId") or response.get("id")
            fee_info = response.get("fee")
            if isinstance(fee_info, dict):
                fee = fee_info.get("cost")
                fee_currency = fee_info.get("currency")
        self.lifecycle_manager.record_event(
            order_id,
            from_enum,
            to_enum,
            message,
            exchange="okx",
            symbol=symbol or (response.get("symbol") if response else None),
            exchange_status=exchange_status,
            exchange_event_ts=exchange_ts,
            raw_payload=payload,
            client_order_id=order_id,
            trade_id=trade_id,
            fill_qty=fill_qty,
            fill_price=fill_price,
            fee=fee,
            fee_currency=fee_currency,
        )

    def _persist_trade(
        self,
        row: dict,
        response: dict,
        filled: Optional[float],
        average_price: Optional[float],
    ) -> None:
        with get_connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM trades WHERE order_id = ? LIMIT 1",
                (row["id"],),
            ).fetchone()
            if exists:
                return

            price = average_price or row.get("price") or 0.0
            amount = filled or row.get("amount") or 0.0
            fee_cost = None
            fee_ccy = None
            fee_info = response.get("fee")
            if isinstance(fee_info, dict):
                fee_cost = fee_info.get("cost")
                fee_ccy = fee_info.get("currency")
            timestamp = response.get("timestamp") or utc_now_ms()

            conn.execute(
                """
                INSERT INTO trades (
                    order_id,
                    symbol,
                    side,
                    price,
                    amount,
                    fee,
                    fee_currency,
                    realized_pnl,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["symbol"],
                    row.get("side") or "unknown",
                    float(price),
                    float(amount),
                    fee_cost,
                    fee_ccy,
                    None,
                    int(timestamp),
                ),
            )
            conn.commit()
