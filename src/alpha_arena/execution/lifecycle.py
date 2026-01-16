"""Order lifecycle event recorder."""

from __future__ import annotations

from typing import Optional

from alpha_arena.db.connection import get_connection
from alpha_arena.models.enums import OrderStatus
from alpha_arena.utils.time import utc_now_s


class OrderLifecycleManager:
    """Record order status transitions into order_lifecycle_events."""

    def __init__(self) -> None:
        self._columns_cache: Optional[set[str]] = None

    def _get_columns(self, conn) -> set[str]:
        if self._columns_cache is None:
            rows = conn.execute("PRAGMA table_info(order_lifecycle_events)").fetchall()
            self._columns_cache = {row["name"] for row in rows}
        return self._columns_cache

    def record_event(
        self,
        order_id: str,
        from_status: Optional[OrderStatus],
        to_status: OrderStatus,
        message: str,
        *,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        exchange_status: Optional[str] = None,
        exchange_event_ts: Optional[int] = None,
        raw_payload: Optional[str] = None,
        client_order_id: Optional[str] = None,
        trade_id: Optional[str] = None,
        fill_qty: Optional[float] = None,
        fill_price: Optional[float] = None,
        fee: Optional[float] = None,
        fee_currency: Optional[str] = None,
    ) -> None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM orders WHERE client_order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone()
            if not row:
                return
            columns = self._get_columns(conn)
            from_value = from_status.value if from_status else "UNKNOWN"
            details = f"{from_value} -> {to_status.value}. {message}"

            fields = ["order_id", "status", "message", "timestamp"]
            values = [row["id"], to_status.value, details, utc_now_s()]

            optional_fields = {
                "exchange": exchange,
                "symbol": symbol,
                "exchange_status": exchange_status,
                "exchange_event_ts": exchange_event_ts,
                "raw_payload": raw_payload,
                "client_order_id": client_order_id,
                "trade_id": trade_id,
                "fill_qty": fill_qty,
                "fill_price": fill_price,
                "fee": fee,
                "fee_currency": fee_currency,
            }
            for key, value in optional_fields.items():
                if key in columns:
                    fields.append(key)
                    values.append(value)

            placeholders = ", ".join(["?"] * len(values))
            conn.execute(
                f"""
                INSERT INTO order_lifecycle_events ({", ".join(fields)})
                VALUES ({placeholders})
                """,
                tuple(values),
            )
            conn.commit()
