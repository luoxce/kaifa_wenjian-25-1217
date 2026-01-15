"""Decision engine that persists LLM selections."""

from __future__ import annotations

import json
from typing import Optional

from alpha_arena.data.models import DecisionRecord
from alpha_arena.db.connection import get_connection
from alpha_arena.decision.models import DecisionResult
from alpha_arena.decision.selector import LLMStrategySelector


class DecisionEngine:
    """Orchestrate data -> LLM selection -> persistence."""

    def __init__(self, selector: Optional[LLMStrategySelector] = None) -> None:
        self.selector = selector or LLMStrategySelector()

    def decide(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> Optional[DecisionResult]:
        result = self.selector.select(symbol, timeframe, limit=limit)
        if result is None and self.selector.last_result is not None:
            self._persist(self.selector.last_result, accepted=False)
            return None
        if result is None:
            return None
        self._persist(result, accepted=result.accepted)
        return result

    def _persist(self, result: DecisionResult, accepted: bool) -> None:
        action = result.selected_strategy_id or "HOLD"
        reasoning = result.reasoning
        if not accepted:
            action = "HOLD"
            if result.rejection_reason:
                reasoning = f"rejected:{result.rejection_reason} | {reasoning}"

        technical_payload = {
            "indicators": result.indicators,
            "market_data": result.market_data,
            "market_regime": result.market_regime,
            "selected_strategy_id": result.selected_strategy_id,
            "accepted": accepted,
            "rejection_reason": result.rejection_reason,
        }
        record = DecisionRecord(
            symbol=result.symbol,
            timeframe=result.timeframe,
            timestamp=result.timestamp,
            action=action,
            confidence=result.confidence,
            reasoning=reasoning,
            technical_analysis=json.dumps(technical_payload, ensure_ascii=True),
            risk_assessment=None,
            llm_response=result.raw_response,
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
