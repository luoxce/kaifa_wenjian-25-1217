"""Simulated order executor with basic state transitions."""

from __future__ import annotations

import time
from typing import Dict, Optional

from alpha_arena.db.connection import get_connection
from alpha_arena.execution.base_executor import BaseOrderExecutor
from alpha_arena.models.enums import OrderSide, OrderStatus, OrderType
from alpha_arena.models.order import Order
from alpha_arena.utils.time import utc_now_ms, utc_now_s


class SimulatedOrderExecutor(BaseOrderExecutor):
    """Simulated executor that instantly fills orders."""

    def __init__(
        self,
        latency_ms: int = 0,
        risk_manager=None,
        lifecycle_manager=None,
    ) -> None:
        super().__init__(risk_manager=risk_manager, lifecycle_manager=lifecycle_manager)
        self.latency_ms = latency_ms
        self._orders: Dict[str, Order] = {}

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
        order = Order.create(
            symbol=symbol,
            side=side,
            type=type,
            price=price,
            quantity=quantity,
            leverage=leverage,
            confidence=confidence,
            signal_ok=signal_ok,
        )
        self._orders[order.order_id] = order
        self._persist_order(order, is_new=True)

        passed, reason, _rule = self.risk_manager.check(order)
        if not passed:
            rejected = self._transition(order, OrderStatus.REJECTED, reason)
            return rejected

        order = self._transition(order, OrderStatus.NEW)
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)
        order = self._transition(order, OrderStatus.FILLED)
        self._persist_trade(order)
        self._update_position(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id) or self._load_order(order_id)
        if not order:
            return False
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}:
            return False
        order = self._transition(order, OrderStatus.CANCELED)
        self._orders[order_id] = order
        return True

    def get_order(self, order_id: str) -> Order:
        order = self._orders.get(order_id) or self._load_order(order_id)
        if not order:
            raise KeyError(f"Order not found: {order_id}")
        return order

    def _transition(self, order: Order, status: OrderStatus, message: str = "") -> Order:
        updated = order.with_status(status)
        self._orders[updated.order_id] = updated
        self._persist_order(updated, is_new=False)
        self.lifecycle_manager.record_event(order.order_id, order.status, status, message)
        return updated

    def _persist_order(self, order: Order, is_new: bool) -> None:
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
                        f"SIM-{order.order_id}",
                        None,
                        order.created_at,
                        order.updated_at,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE orders
                    SET status = ?, price = ?, amount = ?, leverage = ?, updated_at = ?
                    WHERE client_order_id = ?
                    """,
                    (
                        order.status.value,
                        order.price,
                        order.quantity,
                        order.leverage,
                        order.updated_at,
                        order.order_id,
                    ),
                )
            conn.commit()

    def _persist_trade(self, order: Order) -> None:
        with get_connection() as conn:
            order_row_id = self._get_order_row_id(conn, order.order_id)
            if not order_row_id:
                return
            exists = conn.execute(
                "SELECT 1 FROM trades WHERE order_id = ? LIMIT 1",
                (order_row_id,),
            ).fetchone()
            if exists:
                return
            price = order.price or 0.0
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
                    float(order.quantity),
                    None,
                    None,
                    None,
                    utc_now_ms(),
                ),
            )
            conn.commit()

    def _update_position(self, order: Order) -> None:
        qty = float(order.quantity or 0.0)
        if qty <= 0:
            return
        signed_qty = qty if order.side == OrderSide.BUY else -qty
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT side, size, entry_price
                FROM positions
                WHERE symbol = ?
                ORDER BY updated_at DESC
                """,
                (order.symbol,),
            ).fetchall()
            net_size = 0.0
            entry_price = None
            for row in rows:
                side = (row["side"] or "").lower()
                size = float(row["size"] or 0.0)
                if side in {"long", "buy"}:
                    net_size += size
                elif side in {"short", "sell"}:
                    net_size -= size
                if entry_price is None and row["entry_price"] is not None:
                    entry_price = float(row["entry_price"])

            new_net = net_size + signed_qty
            if abs(new_net) < 1e-8:
                conn.execute("DELETE FROM positions WHERE symbol = ?", (order.symbol,))
                conn.commit()
                return

            price = float(order.price or entry_price or 0.0)
            if net_size == 0 or (net_size * new_net < 0):
                new_entry = price
            elif net_size * signed_qty > 0:
                base_entry = entry_price if entry_price is not None else price
                new_entry = (abs(net_size) * base_entry + abs(signed_qty) * price) / abs(new_net)
            else:
                new_entry = entry_price if entry_price is not None else price

            new_side = "long" if new_net > 0 else "short"
            conn.execute("DELETE FROM positions WHERE symbol = ?", (order.symbol,))
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
                    order.symbol,
                    new_side,
                    abs(new_net),
                    float(new_entry),
                    order.leverage,
                    0.0,
                    None,
                    None,
                    utc_now_s(),
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
                    order.symbol,
                    utc_now_ms(),
                    new_side,
                    abs(new_net),
                    float(new_entry),
                    price,
                    0.0,
                    order.leverage,
                    None,
                    None,
                ),
            )
            conn.commit()

    def _db_order_exists(self, conn, order_id: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM orders WHERE client_order_id = ? LIMIT 1",
            (order_id,),
        ).fetchone()
        return row is not None

    def _get_order_row_id(self, conn, order_id: str) -> Optional[int]:
        row = conn.execute(
            "SELECT id FROM orders WHERE client_order_id = ? LIMIT 1",
            (order_id,),
        ).fetchone()
        if not row:
            return None
        return int(row["id"])

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
