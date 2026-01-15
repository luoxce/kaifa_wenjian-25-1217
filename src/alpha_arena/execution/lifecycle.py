"""Order lifecycle event recorder."""

from __future__ import annotations

from typing import Optional

from alpha_arena.db.connection import get_connection
from alpha_arena.models.enums import OrderStatus
from alpha_arena.utils.time import utc_now_s


class OrderLifecycleManager:
    """Record order status transitions into order_lifecycle_events."""

    def record_event(
        self,
        order_id: str,
        from_status: Optional[OrderStatus],
        to_status: OrderStatus,
        message: str,
    ) -> None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM orders WHERE client_order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone()
            if not row:
                return
            from_value = from_status.value if from_status else "UNKNOWN"
            details = f"{from_value} -> {to_status.value}. {message}"
            conn.execute(
                """
                INSERT INTO order_lifecycle_events (order_id, status, message, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (row["id"], to_status.value, details, utc_now_s()),
            )
            conn.commit()
