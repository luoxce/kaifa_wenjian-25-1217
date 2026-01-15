"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

import pandas as pd

from alpha_arena.data import DataService
from alpha_arena.strategies.signals import StrategySignal


class BaseStrategy(ABC):
    """Strategy interface; strategies read data via DataService only."""

    def __init__(
        self,
        name: str,
        symbol: str,
        timeframe: str,
        data_service: DataService,
        params: Optional[Dict] = None,
        data_limit: int = 300,
    ) -> None:
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_service = data_service
        self.params = params or {}
        self.data_limit = data_limit

    def get_candles(self) -> pd.DataFrame:
        return self.data_service.get_ohlcv(
            self.symbol, self.timeframe, limit=self.data_limit
        )

    @abstractmethod
    def generate_signal(self) -> StrategySignal:
        raise NotImplementedError
