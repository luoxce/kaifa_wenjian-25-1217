"""Prompt builder for LLM strategy selection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user: str


class PromptBuilder:
    """Build system and user prompts for strategy selection."""

    def build(
        self,
        market_data: Dict,
        technical_indicators: Dict,
        active_strategies: Iterable[Dict],
        regime_context: Optional[Dict] = None,
        decision_feedback: Optional[str] = None,
    ) -> PromptBundle:
        strategies_payload: List[Dict] = []
        for item in active_strategies:
            strategies_payload.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "description": item.get("description"),
                }
            )

        system_prompt = (
            "You are a quant strategy allocator. "
            "Return JSON only. No markdown, no extra text. "
            "Use this schema exactly:\n"
            "{\n"
            '  "market_regime": "TREND|RANGE|BREAKOUT|STRONG_TREND|WEAK_TREND|HIGH_VOLATILITY|LOW_VOLATILITY",\n'
            '  "strategy_allocations": [\n'
            "    {\n"
            '      "strategy_id": "string",\n'
            '      "weight": 0.0,\n'
            '      "confidence": 0.0,\n'
            '      "reasoning": "string"\n'
            "    }\n"
            "  ],\n"
            '  "total_position": 0.0,\n'
            '  "confidence": 0.0,\n'
            '  "reasoning": "string"\n'
            "}\n"
            "Rules:\n"
            "- strategy_id must be one of the provided strategies.\n"
            "- strategy_allocations weights must sum to 1.0 (+/- 0.05).\n"
            "- total_position must be between -1 and 1.\n"
            "- confidence must be between 0 and 1.\n"
            "- If only one strategy is suitable, return a single allocation with weight 1.0.\n"
            "- If no strategy is suitable, return an empty strategy_allocations list, total_position 0, and confidence 0.\n"
            "- Legacy fallback: you may also include selected_strategy_id (or HOLD) for compatibility.\n"
            "- Use market_regime_context (current + last 5 periods + signals) to guide selection.\n"
            "Example:\n"
            "{\n"
            '  "market_regime": "TREND",\n'
            '  "strategy_allocations": [\n'
            '    {"strategy_id": "ema_trend", "weight": 0.6, "confidence": 0.85, "reasoning": "strong trend"},\n'
            '    {"strategy_id": "momentum", "weight": 0.3, "confidence": 0.75, "reasoning": "momentum confirmation"},\n'
            '    {"strategy_id": "breakout", "weight": 0.1, "confidence": 0.65, "reasoning": "breakout assist"}\n'
            "  ],\n"
            '  "total_position": 0.8,\n'
            '  "confidence": 0.80,\n'
            '  "reasoning": "multi-strategy blend for stability"\n'
            "}\n"
        )

        user_payload = {
            "market_data": market_data,
            "technical_indicators": technical_indicators,
            "active_strategies": strategies_payload,
        }
        if regime_context:
            user_payload["market_regime_context"] = regime_context
        feedback_block = ""
        if decision_feedback:
            feedback_block = decision_feedback.strip() + "\n\n"
        user_prompt = (
            feedback_block
            + "Select the best strategy mix based on the data below.\n"
            + json.dumps(user_payload, ensure_ascii=True, indent=2)
        )
        return PromptBundle(system=system_prompt, user=user_prompt)
