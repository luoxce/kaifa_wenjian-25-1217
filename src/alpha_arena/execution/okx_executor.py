"""OKX order executor (stub) with risk checks and lifecycle logging."""

from __future__ import annotations

import time
from typing import Dict, Iterable, Optional, Tuple

from alpha_arena.db.connection import get_connection
from alpha_arena.execution.base_executor import BaseOrderExecutor
from alpha_arena.ingest.okx import create_okx_client
from alpha_arena.config import settings
from alpha_arena.models.enums import OrderSide, OrderStatus, OrderType
from alpha_arena.models.order import Order
from alpha_arena.utils.time import utc_now_ms, utc_now_s


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value.strip() == "":
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class OKXOrderExecutor(BaseOrderExecutor):
    """OKX executor with risk checks and status persistence."""

    def __init__(
        self,
        latency_ms: int = 0,
        risk_manager=None,
        lifecycle_manager=None,
    ) -> None:
        super().__init__(risk_manager=risk_manager, lifecycle_manager=lifecycle_manager)
        self.exchange = create_okx_client()
        self.exchange.load_markets()
        self.latency_ms = latency_ms
        self._orders: Dict[str, Order] = {}
        self._exchange_ids: Dict[str, str] = {}

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        leverage: Optional[float] = None,
        confidence: Optional[float] = None,
        signal_ok: Optional[bool] = None,
    ) -> Order:
        effective_price = price
        if effective_price is None:
            effective_price = self._estimate_price(symbol)
        order = Order.create(
            symbol=symbol,
            side=side,
            type=type,
            price=effective_price,
            quantity=quantity,
            leverage=leverage,
            confidence=confidence,
            signal_ok=signal_ok,
        )
        self._persist_order(order, is_new=True)

        passed, reason, _rule = self.risk_manager.check(order)
        if not passed:
            rejected = self._transition(order, OrderStatus.REJECTED, reason)
            self._orders[order.order_id] = rejected
            return rejected

        if type == OrderType.LIMIT and effective_price is None:
            rejected = self._transition(order, OrderStatus.REJECTED, "limit order missing price")
            self._orders[order.order_id] = rejected
            return rejected

        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)

        params = self._build_params(side)
        response, params = self._submit_with_posside_retry(
            symbol=symbol,
            side=side,
            type=type,
            quantity=quantity,
            price=price,
            params=params,
            order=order,
        )
        if response is None:
            return self._orders.get(order.order_id, order)
        exchange_id = response.get("id")

        order = self._transition(order, OrderStatus.NEW, "exchange accepted")
        self._persist_order(order, is_new=False, exchange_order_id=exchange_id)

        mapped_status = self._map_status(response, order)
        if mapped_status != order.status:
            order = self._transition(order, mapped_status, "exchange status update")
            self._persist_order(order, is_new=False, exchange_order_id=exchange_id)

        self._orders[order.order_id] = order
        if exchange_id:
            self._exchange_ids[order.order_id] = exchange_id
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id) or self._load_order(order_id)
        if not order:
            return False
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
            return False

        exchange_id = self._exchange_ids.get(order_id)
        if exchange_id:
            self.exchange.cancel_order(exchange_id, order.symbol)

        order = self._transition(order, OrderStatus.CANCELED, "cancel requested")
        self._persist_order(order, is_new=False, exchange_order_id=exchange_id)
        self._orders[order_id] = order
        return True

    def get_order(self, order_id: str) -> Order:
        order = self._orders.get(order_id) or self._load_order(order_id)
        if not order:
            raise KeyError(f"Order not found: {order_id}")
        return order

    def refresh_order_status(self, order_id: str) -> Order:
        order = self._orders.get(order_id) or self._load_order(order_id)
        if not order:
            raise KeyError(f"Order not found: {order_id}")
        exchange_id = self._exchange_ids.get(order_id) or self._load_exchange_order_id(order_id)
        if not exchange_id:
            return order
        try:
            response = self.exchange.fetch_order(exchange_id, order.symbol)
        except Exception:
            return order

        new_status = self._map_status(response, order)
        if new_status != order.status:
            order = self._transition(order, new_status, "exchange refresh")
            self._orders[order.order_id] = order

        if new_status == OrderStatus.FILLED:
            self._persist_trade(order, response)
        return order

    def wait_for_fill(
        self,
        order_id: str,
        timeout_s: float = 8.0,
        poll_interval_s: float = 1.0,
    ) -> Order:
        start = time.time()
        order = self.get_order(order_id)
        while time.time() - start < timeout_s:
            order = self.refresh_order_status(order_id)
            if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
                return order
            time.sleep(poll_interval_s)
        return order

    def sync_account_state(self, symbols: Optional[Iterable[str]] = None) -> None:
        self._sync_balances()
        self._sync_positions(symbols)

    def _estimate_price(self, symbol: str) -> Optional[float]:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
        except Exception:
            return None
        return ticker.get("last") or ticker.get("mark") or ticker.get("index")

    def _map_status(self, response: dict, order: Order) -> OrderStatus:
        status = (response.get("status") or "").lower()
        filled = response.get("filled") or 0
        amount = response.get("amount") or order.quantity

        if status in {"canceled", "cancelled"}:
            return OrderStatus.CANCELED
        if status in {"rejected"}:
            return OrderStatus.REJECTED
        if amount and filled:
            if filled >= amount:
                return OrderStatus.FILLED
            return OrderStatus.PARTIALLY_FILLED
        if status in {"closed", "filled"}:
            return OrderStatus.FILLED
        return OrderStatus.NEW

    def _transition(self, order: Order, status: OrderStatus, message: str) -> Order:
        updated = order.with_status(status)
        self._persist_order(updated, is_new=False)
        self.lifecycle_manager.record_event(order.order_id, order.status, status, message)
        return updated

    def _build_params(self, side: OrderSide) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if settings.okx_td_mode:
            params["tdMode"] = settings.okx_td_mode
        if settings.okx_default_market == "swap":
            pos_mode = (settings.okx_pos_mode or "").strip().lower()
            if pos_mode in {"long_short", "hedge", "longshort"}:
                params["posSide"] = "long" if side == OrderSide.BUY else "short"
        return params

    def _submit_with_posside_retry(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: float,
        price: Optional[float],
        params: Dict[str, str],
        order: Order,
    ) -> Tuple[Optional[dict], Dict[str, str]]:
        try:
            response = self.exchange.create_order(
                symbol,
                type.value.lower(),
                side.value.lower(),
                quantity,
                price,
                params,
            )
            return response, params
        except Exception as exc:
            message = str(exc)
            if settings.okx_default_market != "swap" or "posSide" not in message:
                rejected = self._transition(order, OrderStatus.REJECTED, f"exchange error: {message}")
                self._orders[order.order_id] = rejected
                return None, params

            retry_params = dict(params)
            if "posSide" in retry_params:
                retry_params.pop("posSide", None)
            else:
                retry_params["posSide"] = "long" if side == OrderSide.BUY else "short"
            try:
                response = self.exchange.create_order(
                    symbol,
                    type.value.lower(),
                    side.value.lower(),
                    quantity,
                    price,
                    retry_params,
                )
                return response, retry_params
            except Exception as retry_exc:
                rejected = self._transition(
                    order,
                    OrderStatus.REJECTED,
                    f"exchange error: {retry_exc}",
                )
                self._orders[order.order_id] = rejected
                return None, params

    def _load_exchange_order_id(self, order_id: str) -> Optional[str]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT exchange_order_id FROM orders WHERE client_order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone()
        if not row:
            return None
        return row["exchange_order_id"]

    def _get_order_row_id(self, order_id: str) -> Optional[int]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM orders WHERE client_order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone()
        if not row:
            return None
        return int(row["id"])

    def _persist_trade(self, order: Order, response: dict) -> None:
        order_row_id = self._get_order_row_id(order.order_id)
        if not order_row_id:
            return
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT 1 FROM trades WHERE order_id = ? LIMIT 1",
                (order_row_id,),
            ).fetchone()
            if existing:
                return

            filled = response.get("filled")
            if filled is None:
                filled = response.get("amount") or order.quantity
            price = response.get("average") or response.get("price") or order.price or 0.0
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
                    order_row_id,
                    order.symbol,
                    order.side.value,
                    float(price),
                    float(filled),
                    fee_cost,
                    fee_ccy,
                    None,
                    int(timestamp),
                ),
            )
            conn.commit()

    def _sync_balances(self) -> None:
        try:
            balance = self.exchange.fetch_balance()
        except Exception:
            return
        timestamp = balance.get("timestamp") or utc_now_ms()
        totals = balance.get("total") or {}
        frees = balance.get("free") or {}
        used = balance.get("used") or {}
        with get_connection() as conn:
            for currency, total in totals.items():
                total_value = _safe_float(total)
                if total_value is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO balances (currency, timestamp, total, free, used)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(currency, timestamp) DO NOTHING
                    """,
                    (
                        currency,
                        int(timestamp),
                        total_value,
                        _safe_float(frees.get(currency)),
                        _safe_float(used.get(currency)),
                    ),
                )
            conn.commit()

    def _sync_positions(self, symbols: Optional[Iterable[str]] = None) -> None:
        symbol_list = [s for s in symbols] if symbols else []
        try:
            positions = (
                self.exchange.fetch_positions(symbol_list)
                if symbol_list
                else self.exchange.fetch_positions()
            )
        except Exception:
            return

        now_ms = utc_now_ms()
        now_s = utc_now_s()
        parsed_positions = []
        active_keys = set()
        for pos in positions:
            symbol = pos.get("symbol") or pos.get("info", {}).get("instId")
            if not symbol:
                continue
            if symbol_list and symbol not in symbol_list:
                continue

            size = (
                pos.get("contracts")
                or pos.get("position")
                or pos.get("size")
                or pos.get("info", {}).get("pos")
            )
            size_value = _safe_float(size)
            if size_value is None or size_value == 0:
                continue

            side = pos.get("side") or pos.get("info", {}).get("posSide")
            if side:
                side = side.lower()
            if side in {"net", "both", "none", ""} or side is None:
                side = "long" if size_value > 0 else "short"

            entry_price = (
                pos.get("entryPrice")
                or pos.get("avgPrice")
                or pos.get("info", {}).get("avgPx")
                or pos.get("info", {}).get("avgPrice")
            )
            entry_price_value = _safe_float(entry_price)
            if entry_price_value is None:
                entry_price_value = _safe_float(
                    pos.get("markPrice") or pos.get("info", {}).get("markPx")
                ) or 0.0

            mark_price = _safe_float(
                pos.get("markPrice") or pos.get("info", {}).get("markPx")
            )
            unrealized = _safe_float(
                pos.get("unrealizedPnl") or pos.get("info", {}).get("upl")
            )
            leverage = _safe_float(
                pos.get("leverage") or pos.get("info", {}).get("lever")
            )
            margin = _safe_float(
                pos.get("margin") or pos.get("info", {}).get("margin")
            )
            liquidation = _safe_float(
                pos.get("liquidationPrice") or pos.get("info", {}).get("liqPx")
            )

            parsed_positions.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "size": size_value,
                    "entry_price": entry_price_value,
                    "mark_price": mark_price,
                    "unrealized": unrealized,
                    "leverage": leverage,
                    "margin": margin,
                    "liquidation": liquidation,
                }
            )
            active_keys.add((symbol, side))

        with get_connection() as conn:
            if symbol_list:
                placeholders = ",".join("?" for _ in symbol_list)
                existing_rows = conn.execute(
                    f"SELECT symbol, side, size, entry_price FROM positions WHERE symbol IN ({placeholders})",
                    tuple(symbol_list),
                ).fetchall()
            else:
                existing_rows = conn.execute(
                    "SELECT symbol, side, size, entry_price FROM positions"
                ).fetchall()

            for row in existing_rows:
                key = (row["symbol"], row["side"])
                if key in active_keys:
                    continue
                conn.execute(
                    """
                    INSERT INTO position_snapshots (
                        symbol,
                        timestamp,
                        side,
                        size,
                        entry_price,
                        mark_price,
                        unrealized_pnl,
                        leverage,
                        margin,
                        liquidation_price
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timestamp, side) DO NOTHING
                    """,
                    (
                        row["symbol"],
                        int(now_ms),
                        row["side"],
                        0.0,
                        float(row["entry_price"]) if row["entry_price"] is not None else 0.0,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                )

            if symbol_list:
                placeholders = ",".join("?" for _ in symbol_list)
                conn.execute(
                    f"DELETE FROM positions WHERE symbol IN ({placeholders})",
                    tuple(symbol_list),
                )
            else:
                conn.execute("DELETE FROM positions")

            for pos in parsed_positions:
                conn.execute(
                    """
                    INSERT INTO positions (
                        symbol,
                        side,
                        size,
                        entry_price,
                        leverage,
                        unrealized_pnl,
                        margin,
                        liquidation_price,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pos["symbol"],
                        pos["side"],
                        abs(pos["size"]),
                        float(pos["entry_price"]),
                        pos["leverage"],
                        pos["unrealized"],
                        pos["margin"],
                        pos["liquidation"],
                        int(now_s),
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO position_snapshots (
                        symbol,
                        timestamp,
                        side,
                        size,
                        entry_price,
                        mark_price,
                        unrealized_pnl,
                        leverage,
                        margin,
                        liquidation_price
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timestamp, side) DO NOTHING
                    """,
                    (
                        pos["symbol"],
                        int(now_ms),
                        pos["side"],
                        abs(pos["size"]),
                        float(pos["entry_price"]),
                        pos["mark_price"],
                        pos["unrealized"],
                        pos["leverage"],
                        pos["margin"],
                        pos["liquidation"],
                    ),
                )
            conn.commit()

    def _persist_order(
        self,
        order: Order,
        is_new: bool,
        exchange_order_id: Optional[str] = None,
    ) -> None:
        with get_connection() as conn:
            if is_new and not self._db_order_exists(conn, order.order_id):
                conn.execute(
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
                        order.symbol,
                        order.side.value,
                        order.type.value,
                        order.price,
                        order.quantity,
                        order.leverage,
                        order.status.value,
                        order.order_id,
                        exchange_order_id,
                        None,
                        order.created_at,
                        order.updated_at,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE orders
                    SET status = ?, price = ?, amount = ?, leverage = ?, updated_at = ?, exchange_order_id = ?
                    WHERE client_order_id = ?
                    """,
                    (
                        order.status.value,
                        order.price,
                        order.quantity,
                        order.leverage,
                        order.updated_at,
                        exchange_order_id,
                        order.order_id,
                    ),
                )
            conn.commit()

    def _db_order_exists(self, conn, order_id: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM orders WHERE client_order_id = ? LIMIT 1",
            (order_id,),
        ).fetchone()
        return row is not None

    def _load_order(self, order_id: str) -> Optional[Order]:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT symbol, side, type, price, amount, leverage, status, client_order_id, created_at, updated_at
                FROM orders
                WHERE client_order_id = ?
                LIMIT 1
                """,
                (order_id,),
            ).fetchone()
        if not row:
            return None
        return Order(
            order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=OrderSide(row["side"]),
            type=OrderType(row["type"]),
            price=row["price"],
            quantity=row["amount"],
            leverage=row["leverage"],
            status=OrderStatus(row["status"]),
            confidence=None,
            signal_ok=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
