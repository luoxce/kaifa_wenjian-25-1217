"""Technical indicator helpers for strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist},
        index=series.index,
    )


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (trend strength)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_val = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_val.replace(0, pd.NA))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_val.replace(0, pd.NA))
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA) * 100
    return dx.rolling(window=period).mean()


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    bandwidth = (upper - lower) / mid.replace(0, pd.NA)
    return pd.DataFrame(
        {"upper": upper, "mid": mid, "lower": lower, "bandwidth": bandwidth},
        index=series.index,
    )


def volume_ma(series: pd.Series, period: int = 20) -> pd.Series:
    return series.rolling(window=period).mean()


def atr_percentile(df: pd.DataFrame, period: int = 14, lookback: int = 100) -> pd.Series:
    atr_series = atr(df, period)

    def _percentile(window: np.ndarray) -> float:
        current = window[-1]
        if np.isnan(current):
            return 0.0
        values = window[~np.isnan(window)]
        if values.size == 0:
            return 0.0
        sorted_vals = np.sort(values)
        rank = np.searchsorted(sorted_vals, current, side="right")
        return (rank / sorted_vals.size) * 100.0

    return atr_series.rolling(window=lookback, min_periods=2).apply(
        _percentile, raw=True
    ).fillna(0.0)


def price_efficiency(df: pd.DataFrame, period: int = 20) -> pd.Series:
    close = df["close"].astype(float)
    net_change = close.diff(period).abs()
    total_move = close.diff().abs().rolling(window=period).sum()
    efficiency = net_change / total_move.replace(0, pd.NA)
    return efficiency.fillna(0.0)


def volume_trend(df: pd.DataFrame, period: int = 20) -> pd.Series:
    volume = df["volume"].astype(float).fillna(0.0)
    vol_ma = volume.rolling(window=period).mean()
    prev_ma = vol_ma.shift(period)
    trend = (vol_ma - prev_ma) / prev_ma.replace(0, pd.NA)
    return trend.fillna(0.0)
