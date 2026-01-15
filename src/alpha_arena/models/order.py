"""Order model and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from alpha_arena.models.enums import OrderSide, OrderStatus, OrderType
from alpha_arena.utils.time import utc_now_s


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: Optional[float]
    quantity: float
    leverage: Optional[float]
    status: OrderStatus
    confidence: Optional[float]
    signal_ok: Optional[bool]
    created_at: int
    updated_at: int

    @classmethod
    def create(
        cls,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        price: Optional[float],
        quantity: float,
        leverage: Optional[float] = None,
        confidence: Optional[float] = None,
        signal_ok: Optional[bool] = None,
    ) -> "Order":
        now = utc_now_s()
        return cls(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            type=type,
            price=price,
            quantity=quantity,
            leverage=leverage,
            status=OrderStatus.CREATED,
            confidence=confidence,
            signal_ok=signal_ok,
            created_at=now,
            updated_at=now,
        )

    def with_status(self, status: OrderStatus) -> "Order":
        return Order(
            order_id=self.order_id,
            symbol=self.symbol,
            side=self.side,
            type=self.type,
            price=self.price,
            quantity=self.quantity,
            leverage=self.leverage,
            status=status,
            confidence=self.confidence,
            signal_ok=self.signal_ok,
            created_at=self.created_at,
            updated_at=utc_now_s(),
        )
