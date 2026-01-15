"""Order tracking and lifecycle updates for live orders."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from alpha_arena.db.connection import get_connection
from alpha_arena.execution.lifecycle import OrderLifecycleManager
from alpha_arena.ingest.okx import create_okx_client
from alpha_arena.models.enums import OrderStatus
from alpha_arena.utils.time import utc_now_ms, utc_now_s


logger = logging.getLogger(__name__)


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
            )

        status_changed = new_status.value != old_status
        if status_changed:
            event = self._event_name(new_status)
            self._record_event(
                row["client_order_id"],
                old_status,
                new_status.value,
                event,
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

    def _record_event(self, order_id: str, from_status: str, to_status: str, message: str) -> None:
        try:
            from_enum = OrderStatus(from_status) if from_status else None
        except Exception:
            from_enum = None
        to_enum = OrderStatus(to_status)
        self.lifecycle_manager.record_event(order_id, from_enum, to_enum, message)

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
