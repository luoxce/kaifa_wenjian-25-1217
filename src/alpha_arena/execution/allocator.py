"""Portfolio allocator: decisions -> target positions -> orders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.models.enums import OrderSide, OrderType
from alpha_arena.models.order import Order


@dataclass(frozen=True)
class AllocationPlan:
    strategy_id: str
    weight: float
    target_notional: float


class PortfolioAllocator:
    """Translate strategy weights into executable orders."""

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        global_leverage: Optional[float] = None,
        diff_threshold: Optional[float] = None,
        min_notional: Optional[float] = None,
    ) -> None:
        self.data_service = data_service or DataService()
        self.global_leverage = (
            global_leverage
            if global_leverage is not None
            else settings.portfolio_global_leverage
        )
        self.diff_threshold = (
            diff_threshold
            if diff_threshold is not None
            else settings.portfolio_diff_threshold
        )
        self.min_notional = (
            min_notional
            if min_notional is not None
            else settings.portfolio_min_notional
        )

    def build_orders(
        self,
        symbol: str,
        decisions: Dict[str, float],
        total_equity: float,
        current_positions: Iterable[Dict],
        price: Optional[float] = None,
        leverage: Optional[float] = None,
    ) -> Tuple[List[Order], List[AllocationPlan]]:
        """Return orders (CREATED) plus allocation plan for logging."""
        if total_equity <= 0:
            return [], []

        plan = self._build_plan(decisions, total_equity)
        effective_price = price or self._get_latest_price(symbol)
        if not effective_price or effective_price <= 0:
            return [], plan

        current_notional = self._current_notional(current_positions, effective_price)
        target_notional = sum(item.target_notional for item in plan)
        diff = target_notional - current_notional

        if abs(diff) < self.diff_threshold:
            return [], plan
        if self.min_notional > 0 and abs(diff) < self.min_notional:
            return [], plan

        side = OrderSide.BUY if diff > 0 else OrderSide.SELL
        quantity = abs(diff) / effective_price
        order = Order.create(
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            price=effective_price,
            quantity=quantity,
            leverage=leverage or self.global_leverage,
            confidence=None,
            signal_ok=True,
        )
        return [order], plan

    def _build_plan(self, decisions: Dict[str, float], total_equity: float) -> List[AllocationPlan]:
        plans: List[AllocationPlan] = []
        for strategy_id, weight in decisions.items():
            if weight == 0:
                continue
            target = total_equity * weight * self.global_leverage
            plans.append(
                AllocationPlan(
                    strategy_id=strategy_id,
                    weight=weight,
                    target_notional=target,
                )
            )
        return plans

    def _get_latest_price(self, symbol: str) -> Optional[float]:
        snapshot = self.data_service.get_latest_prices(symbol)
        if snapshot and snapshot.last:
            return snapshot.last
        candles = self.data_service.get_candles(symbol, "1h", limit=1)
        if candles.empty:
            return None
        return float(candles.iloc[-1]["close"])

    def _current_notional(self, positions: Iterable[Dict], price: float) -> float:
        total = 0.0
        for pos in positions:
            size = pos.get("size")
            if size is None:
                size = pos.get("amount")
            if size is None:
                continue
            side = (pos.get("side") or "").lower()
            sign = 1.0 if side in {"long", "buy"} else -1.0 if side in {"short", "sell"} else 0.0
            total += float(size) * price * sign
        return total
