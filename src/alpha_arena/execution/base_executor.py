"""Abstract order executor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from alpha_arena.execution.lifecycle import OrderLifecycleManager
from alpha_arena.models.order import Order
from alpha_arena.models.enums import OrderSide, OrderType
from alpha_arena.risk.manager import RiskManager


class BaseOrderExecutor(ABC):
    """Standard executor interface for backtest and live trading."""

    def __init__(
        self,
        risk_manager: Optional[RiskManager] = None,
        lifecycle_manager: Optional[OrderLifecycleManager] = None,
    ) -> None:
        self.risk_manager = risk_manager or RiskManager()
        self.lifecycle_manager = lifecycle_manager or OrderLifecycleManager()

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        raise NotImplementedError
