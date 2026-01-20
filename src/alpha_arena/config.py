"""Configuration loader for Alpha Arena."""

from dataclasses import dataclass
import os
from typing import Tuple

from dotenv import load_dotenv


def _get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_csv(value: str | None, default: Tuple[str, ...]) -> Tuple[str, ...]:
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _get_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_provider: str
    llm_api_base: str
    llm_api_key: str
    llm_model: str
    deepseek_api_key: str
    deepseek_api_base: str
    deepseek_model: str
    openai_api_key: str
    openai_api_base: str
    openai_model: str
    grok_api_key: str
    grok_api_base: str
    grok_model: str
    gemini_api_key: str
    gemini_api_base: str
    gemini_model: str
    ollama_api_base: str
    ollama_model: str
    vllm_api_base: str
    vllm_model: str
    regime_adx_threshold: float
    regime_bb_width_threshold: float
    portfolio_global_leverage: float
    portfolio_diff_threshold: float
    portfolio_min_notional: float
    okx_td_mode: str
    okx_pos_mode: str
    okx_api_key: str
    okx_api_secret: str
    okx_password: str
    okx_is_demo: bool
    okx_default_symbol: str
    okx_default_market: str
    okx_timeframes: Tuple[str, ...]
    okx_wait_fill: bool
    okx_fill_timeout_s: float
    okx_fill_interval_s: float
    okx_sync_account: bool
    trading_enabled: bool
    api_write_enabled: bool
    risk_max_notional: float
    risk_max_leverage: float
    risk_min_confidence: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/alpha_arena.db"),
            llm_provider=os.getenv("LLM_PROVIDER", "deepseek"),
            llm_api_base=os.getenv("LLM_API_BASE", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_api_base=os.getenv(
                "DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            grok_api_key=os.getenv("GROK_API_KEY", ""),
            grok_api_base=os.getenv("GROK_API_BASE", "https://api.x.ai/v1"),
            grok_model=os.getenv("GROK_MODEL", "grok-2-mini"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_api_base=os.getenv(
                "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai"
            ),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            ollama_api_base=os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1"),
            ollama_model=os.getenv("OLLAMA_MODEL", ""),
            vllm_api_base=os.getenv("VLLM_API_BASE", "http://localhost:8000/v1"),
            vllm_model=os.getenv("VLLM_MODEL", ""),
            regime_adx_threshold=_get_float(os.getenv("REGIME_ADX_THRESHOLD"), 25.0),
            regime_bb_width_threshold=_get_float(
                os.getenv("REGIME_BB_WIDTH_THRESHOLD"), 0.04
            ),
            portfolio_global_leverage=_get_float(
                os.getenv("PORTFOLIO_GLOBAL_LEVERAGE"), 1.0
            ),
            portfolio_diff_threshold=_get_float(
                os.getenv("PORTFOLIO_DIFF_THRESHOLD"), 10.0
            ),
            portfolio_min_notional=_get_float(
                os.getenv("PORTFOLIO_MIN_NOTIONAL"), 10.0
            ),
            okx_td_mode=os.getenv("OKX_TD_MODE", "cross"),
            okx_pos_mode=os.getenv("OKX_POS_MODE", "long_short"),
            okx_api_key=os.getenv("OKX_API_KEY", ""),
            okx_api_secret=os.getenv("OKX_API_SECRET", ""),
            okx_password=os.getenv("OKX_PASSWORD", ""),
            okx_is_demo=_get_bool(os.getenv("OKX_IS_DEMO"), default=True),
            okx_default_symbol=os.getenv("OKX_DEFAULT_SYMBOL", "BTC/USDT:USDT"),
            okx_default_market=os.getenv("OKX_DEFAULT_MARKET", "swap"),
            okx_timeframes=_get_csv(
                os.getenv("OKX_TIMEFRAMES"),
                default=("15m", "1h", "4h", "1d"),
            ),
            okx_wait_fill=_get_bool(os.getenv("OKX_WAIT_FILL"), default=True),
            okx_fill_timeout_s=_get_float(os.getenv("OKX_FILL_TIMEOUT_S"), 8.0),
            okx_fill_interval_s=_get_float(os.getenv("OKX_FILL_INTERVAL_S"), 1.0),
            okx_sync_account=_get_bool(os.getenv("OKX_SYNC_ACCOUNT"), default=True),
            trading_enabled=_get_bool(os.getenv("TRADING_ENABLED"), default=False),
            api_write_enabled=_get_bool(os.getenv("API_WRITE_ENABLED"), default=False),
            risk_max_notional=_get_float(os.getenv("RISK_MAX_NOTIONAL"), 20000.0),
            risk_max_leverage=_get_float(os.getenv("RISK_MAX_LEVERAGE"), 3.0),
            risk_min_confidence=_get_float(os.getenv("RISK_MIN_CONFIDENCE"), 0.6),
        )


settings = Settings.from_env()
