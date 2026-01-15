"""Portfolio decision engine for multi-strategy allocation."""

from __future__ import annotations

import json
from typing import Optional

from alpha_arena.data.models import DecisionRecord
from alpha_arena.db.connection import get_connection
from alpha_arena.decision.portfolio import PortfolioScheduler, StrategyScorer


class PortfolioDecisionEngine:
    """Compute multi-strategy allocations and persist to decisions."""

    def __init__(
        self,
        scorer: Optional[StrategyScorer] = None,
        scheduler: Optional[PortfolioScheduler] = None,
    ) -> None:
        self.scorer = scorer or StrategyScorer()
        self.scheduler = scheduler or PortfolioScheduler()

    def decide(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[dict]:
        allocations, decision = self.scorer.score(symbol, timeframe, limit=limit)
        selected = self.scheduler.allocate(allocations)
        if not selected:
            self._persist(decision, [], accepted=False, reason="no_strategy_selected")
            return None

        self._persist(decision, selected, accepted=True, reason="ok")
        return {
            "symbol": decision.symbol,
            "timeframe": decision.timeframe,
            "timestamp": decision.timestamp,
            "regime": decision.regime,
            "allocations": [
                {
                    "strategy_id": item.strategy_id,
                    "weight": item.weight,
                    "score": item.score,
                    "regime_score": item.regime_score,
                    "performance_score": item.performance_score,
                    "notes": item.notes,
                }
                for item in selected
            ],
            "indicators": decision.indicators,
            "reasoning": decision.reasoning,
        }

    def _persist(
        self,
        decision,
        allocations,
        accepted: bool,
        reason: str,
    ) -> None:
        payload = {
            "regime": decision.regime,
            "indicators": decision.indicators,
            "market_data": decision.market_data,
            "allocations": [
                {
                    "strategy_id": item.strategy_id,
                    "weight": item.weight,
                    "score": item.score,
                    "regime_score": item.regime_score,
                    "performance_score": item.performance_score,
                    "notes": item.notes,
                }
                for item in allocations
            ],
            "accepted": accepted,
            "reason": reason,
        }
        action = "portfolio" if accepted else "HOLD"
        record = DecisionRecord(
            symbol=decision.symbol,
            timeframe=decision.timeframe,
            timestamp=decision.timestamp,
            action=action,
            confidence=None,
            reasoning=decision.reasoning if accepted else reason,
            technical_analysis=json.dumps(payload, ensure_ascii=True),
            risk_assessment=None,
            llm_response=None,
        )
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    symbol,
                    timeframe,
                    timestamp,
                    action,
                    confidence,
                    reasoning,
                    technical_analysis,
                    risk_assessment,
                    llm_response,
                    llm_run_id,
                    prompt_version_id,
                    model_version_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.symbol,
                    record.timeframe,
                    record.timestamp,
                    record.action,
                    record.confidence,
                    record.reasoning,
                    record.technical_analysis,
                    record.risk_assessment,
                    record.llm_response,
                    record.llm_run_id,
                    record.prompt_version_id,
                    record.model_version_id,
                ),
            )
            conn.commit()
