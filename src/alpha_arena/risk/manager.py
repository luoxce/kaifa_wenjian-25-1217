"""Risk management rules and manager."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from alpha_arena.config import settings
from alpha_arena.db.connection import get_connection
from alpha_arena.models.order import Order
from alpha_arena.utils.time import utc_now_s


class RiskRule(ABC):
    name: str

    @abstractmethod
    def check(self, order: Order) -> Tuple[bool, str]:
        raise NotImplementedError


@dataclass(frozen=True)
class MaxNotionalRule(RiskRule):
    max_notional: float
    name: str = "max_notional"

    def check(self, order: Order) -> Tuple[bool, str]:
        if order.price is None:
            return False, "missing price for notional check"
        notional = order.price * order.quantity
        if notional > self.max_notional:
            return False, f"notional {notional:.2f} exceeds max {self.max_notional:.2f}"
        return True, "ok"


@dataclass(frozen=True)
class MaxLeverageRule(RiskRule):
    max_leverage: float
    name: str = "max_leverage"

    def check(self, order: Order) -> Tuple[bool, str]:
        if order.leverage is None:
            return True, "ok"
        if order.leverage > self.max_leverage:
            return False, f"leverage {order.leverage} exceeds max {self.max_leverage}"
        return True, "ok"


@dataclass(frozen=True)
class CircuitBreakerRule(RiskRule):
    min_confidence: float
    name: str = "circuit_breaker"

    def check(self, order: Order) -> Tuple[bool, str]:
        if order.signal_ok is False:
            return False, "signal marked as failed"
        if order.confidence is not None and order.confidence < self.min_confidence:
            return False, f"confidence {order.confidence:.2f} below {self.min_confidence:.2f}"
        return True, "ok"


class RiskManager:
    """Evaluate orders against registered risk rules."""

    def __init__(self, rules: Optional[List[RiskRule]] = None) -> None:
        if rules is None:
            rules = [
                MaxNotionalRule(settings.risk_max_notional),
                MaxLeverageRule(settings.risk_max_leverage),
                CircuitBreakerRule(settings.risk_min_confidence),
            ]
        self.rules = rules

    def check(self, order: Order) -> Tuple[bool, str, str]:
        for rule in self.rules:
            passed, reason = rule.check(order)
            if not passed:
                self._record_event(order, rule.name, reason)
                return False, reason, rule.name
        return True, "ok", ""

    def _record_event(self, order: Order, rule_name: str, reason: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO risk_events (symbol, timestamp, level, rule, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order.symbol, utc_now_s(), "block", rule_name, reason),
            )
            conn.commit()
