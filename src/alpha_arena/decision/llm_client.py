"""Generic LLM client with OpenAI-compatible chat API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Optional, Tuple, Type

import httpx
from pydantic import BaseModel, ValidationError

from alpha_arena.config import settings


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    api_base: str
    model: str
    add_google_key_header: bool = False


class LLMClient:
    """LLM client that supports DeepSeek/OpenAI/Grok/Gemini/local providers."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.provider = (provider or settings.llm_provider or "deepseek").lower()
        self.timeout = timeout
        self.max_retries = max_retries
        self.config = self._resolve_config(api_key=api_key, api_base=api_base, model=model)
        if not self.config.api_base:
            raise ValueError(f"LLM API base missing for provider: {self.provider}")
        if not self.config.model:
            raise ValueError(f"LLM model missing for provider: {self.provider}")

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> Tuple[BaseModel, str]:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                raw = self._chat(system_prompt, user_prompt, temperature, max_tokens)
                payload = _extract_json(raw)
                parsed = response_model.model_validate(payload)
                return parsed, raw
            except (httpx.HTTPError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * attempt)
                    continue
                raise
        raise RuntimeError(f"LLM request failed: {last_error}")

    def _chat(
        self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            if self.config.add_google_key_header:
                headers["x-goog-api-key"] = self.config.api_key

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = self.config.api_base.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or choice.get("text") or ""
        return content.strip()

    def _resolve_config(
        self, api_key: Optional[str], api_base: Optional[str], model: Optional[str]
    ) -> ProviderConfig:
        if settings.llm_api_base or settings.llm_api_key or settings.llm_model:
            return ProviderConfig(
                name=self.provider,
                api_key=api_key or settings.llm_api_key,
                api_base=api_base or settings.llm_api_base,
                model=model or settings.llm_model,
            )

        if self.provider == "openai":
            return ProviderConfig(
                name="openai",
                api_key=api_key or settings.openai_api_key,
                api_base=api_base or settings.openai_api_base,
                model=model or settings.openai_model,
            )
        if self.provider == "grok":
            return ProviderConfig(
                name="grok",
                api_key=api_key or settings.grok_api_key,
                api_base=api_base or settings.grok_api_base,
                model=model or settings.grok_model,
            )
        if self.provider == "gemini":
            return ProviderConfig(
                name="gemini",
                api_key=api_key or settings.gemini_api_key,
                api_base=api_base or settings.gemini_api_base,
                model=model or settings.gemini_model,
                add_google_key_header=True,
            )
        if self.provider == "ollama":
            return ProviderConfig(
                name="ollama",
                api_key=api_key or "",
                api_base=api_base or settings.ollama_api_base,
                model=model or settings.ollama_model,
            )
        if self.provider == "vllm":
            return ProviderConfig(
                name="vllm",
                api_key=api_key or "",
                api_base=api_base or settings.vllm_api_base,
                model=model or settings.vllm_model,
            )
        return ProviderConfig(
            name="deepseek",
            api_key=api_key or settings.deepseek_api_key,
            api_base=api_base or settings.deepseek_api_base,
            model=model or settings.deepseek_model,
        )


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])
