"""Prompt builder for LLM strategy selection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Dict, Iterable, List


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
            "You are a quant strategy selector. "
            "Return JSON only. No markdown, no extra text. "
            "Use this schema exactly:\n"
            "{\n"
            '  "market_regime": "TREND|RANGE|BREAKOUT",\n'
            '  "selected_strategy_id": "string",\n'
            '  "confidence": 0.0,\n'
            '  "reasoning": "string"\n'
            "}\n"
            "Rules:\n"
            "- selected_strategy_id must be one of the provided strategies or HOLD.\n"
            "- confidence must be between 0 and 1.\n"
            "- If no strategy is suitable, set selected_strategy_id to HOLD and confidence to 0.\n"
        )

        user_payload = {
            "market_data": market_data,
            "technical_indicators": technical_indicators,
            "active_strategies": strategies_payload,
        }
        user_prompt = (
            "Select the best strategy based on the data below.\n"
            + json.dumps(user_payload, ensure_ascii=True, indent=2)
        )
        return PromptBundle(system=system_prompt, user=user_prompt)
