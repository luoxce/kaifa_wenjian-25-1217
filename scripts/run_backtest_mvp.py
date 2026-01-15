"""Run a minimal backtest using StrategyLibrary and DataService."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.config import settings
from alpha_arena.data import DataService
from alpha_arena.data.models import FundingSnapshot, PriceSnapshot
from alpha_arena.db.connection import get_connection
from alpha_arena.strategies import SignalType, StrategyLibrary
from alpha_arena.strategies.signals import StrategySignal
from alpha_arena.utils.time import utc_now_s


class BacktestDataService:
    """DataService-compatible view over in-memory backtest data."""

    def __init__(
        self,
        candles: pd.DataFrame,
        funding: Optional[pd.DataFrame] = None,
        prices: Optional[pd.DataFrame] = None,
    ) -> None:
        self._candles = candles.reset_index(drop=True)
        self._funding = None
        if funding is not None and not funding.empty:
            self._funding = funding.sort_values("timestamp").reset_index(drop=True)
        self._prices = prices
        self._index = 0

    def set_index(self, idx: int) -> None:
        self._index = max(0, min(idx, len(self._candles) - 1))

    def _current_ts(self) -> int:
        if self._candles.empty:
            return 0
        return int(self._candles.iloc[self._index]["timestamp"])

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        if self._candles.empty or limit <= 0:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        end = self._index + 1
        window = self._candles.iloc[:end]
        return window.tail(limit).reset_index(drop=True)

    def get_latest_funding(self, symbol: str) -> Optional[FundingSnapshot]:
        if self._funding is None or self._funding.empty:
            return None
        current_ts = self._current_ts()
        if current_ts == 0:
            return None
        eligible = self._funding[self._funding["timestamp"] <= current_ts]
        if eligible.empty:
            return None
        last = eligible.iloc[-1]
        next_ts = last.get("next_funding_time")
        if pd.isna(next_ts):
            next_ts = None
        return FundingSnapshot(
            symbol=symbol,
            timestamp=int(last["timestamp"]),
            funding_rate=float(last["funding_rate"]),
            next_funding_time=int(next_ts) if next_ts is not None else None,
        )

    def get_latest_prices(self, symbol: str) -> Optional[PriceSnapshot]:
        return None


class BacktestRecorder:
    """Persist backtest session, decisions, and orders into the database."""

    def __init__(
        self,
        name: str,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        initial_capital: float,
        fee_rate: float,
        strategy_payload: Dict,
    ) -> None:
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.strategy_payload = strategy_payload
        self._conn = get_connection()
        self.config_id, self.backtest_id = self._start_session()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _start_session(self) -> Tuple[int, int]:
        payload = json.dumps(self.strategy_payload, ensure_ascii=True)
        cur = self._conn.execute(
            """
            INSERT INTO backtest_configs (
                name,
                symbol,
                timeframe,
                start_time,
                end_time,
                initial_capital,
                commission_rate,
                strategy_params
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.name,
                self.symbol,
                self.timeframe,
                self.start_ts,
                self.end_ts,
                self.initial_capital,
                self.fee_rate,
                payload,
            ),
        )
        config_id = int(cur.lastrowid)
        cur = self._conn.execute(
            "INSERT INTO backtest_results (config_id) VALUES (?)", (config_id,)
        )
        backtest_id = int(cur.lastrowid)
        self._conn.commit()
        return config_id, backtest_id

    def record_decision(self, signal: StrategySignal) -> None:
        payload = json.dumps(
            {
                "strategy": signal.strategy,
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "signal_type": signal.signal_type.value,
                "confidence": signal.confidence,
                "timestamp": signal.timestamp,
                "price": signal.price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "position_size": signal.position_size,
                "leverage": signal.leverage,
                "reasoning": signal.reasoning,
            },
            ensure_ascii=True,
        )
        self._conn.execute(
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
                llm_response
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.symbol,
                signal.timeframe,
                signal.timestamp,
                signal.signal_type.value,
                signal.confidence,
                signal.reasoning,
                payload,
                None,
                None,
            ),
        )
        self._conn.execute(
            """
            INSERT INTO backtest_decisions (
                backtest_id,
                timestamp,
                action,
                confidence,
                reasoning
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.backtest_id,
                signal.timestamp,
                signal.signal_type.value,
                signal.confidence,
                signal.reasoning,
            ),
        )
        self._conn.commit()

    def record_order(
        self,
        timestamp: int,
        side: str,
        price: float,
        amount: float,
        fee: float,
        pnl: Optional[float],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO backtest_orders (
                backtest_id,
                timestamp,
                side,
                price,
                amount,
                fee,
                pnl
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.backtest_id,
                timestamp,
                side,
                price,
                amount,
                fee,
                pnl,
            ),
        )
        self._conn.commit()

    def finalize(self, results: Dict, metrics: Dict[str, float]) -> None:
        self._conn.execute(
            """
            UPDATE backtest_results
            SET total_return = ?,
                max_drawdown = ?,
                sharpe_ratio = ?,
                profit_factor = ?,
                total_trades = ?,
                profitable_trades = ?,
                win_rate = ?,
                final_equity = ?,
                equity_curve = ?,
                trade_log = ?
            WHERE id = ?
            """,
            (
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                metrics.get("sharpe_ratio"),
                metrics.get("profit_factor"),
                metrics["total_trades"],
                metrics["profitable_trades"],
                metrics["win_rate_pct"],
                results["final_equity"],
                json.dumps(results["equity_curve"], ensure_ascii=True),
                json.dumps(results["trade_log"], ensure_ascii=True),
                self.backtest_id,
            ),
        )
        self._conn.commit()


class SimpleBacktester:
    """Minimal backtester with market-close execution."""

    def __init__(self, initial_capital: float = 10000.0, fee_rate: float = 0.0005) -> None:
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate

    def run(
        self,
        candles: pd.DataFrame,
        strategy,
        data_service: BacktestDataService,
        recorder: Optional[BacktestRecorder] = None,
    ) -> Dict:
        equity = self.initial_capital
        position = 0  # 1 = long, -1 = short, 0 = flat
        entry_price: Optional[float] = None
        entry_equity: Optional[float] = None
        entry_ts: Optional[int] = None
        position_qty: Optional[float] = None

        trade_log: List[Dict] = []
        equity_curve: List[Dict] = []

        for idx in range(len(candles)):
            data_service.set_index(idx)
            row = candles.iloc[idx]
            price = float(row["close"])
            ts = int(row["timestamp"])
            signal = strategy.generate_signal()
            if recorder is not None:
                recorder.record_decision(signal)

            def close_position(reason: str) -> None:
                nonlocal equity, position, entry_price, entry_equity, entry_ts, position_qty
                if position == 0 or entry_price is None or entry_equity is None:
                    return
                if position == 1:
                    gross_equity = entry_equity * (price / entry_price)
                else:
                    gross_equity = entry_equity * (entry_price / price)
                fee = gross_equity * self.fee_rate
                exit_equity = gross_equity - fee
                pnl = exit_equity - entry_equity
                if recorder is not None:
                    side = "sell" if position == 1 else "buy"
                    recorder.record_order(
                        ts,
                        side,
                        price,
                        position_qty or 0.0,
                        fee,
                        pnl,
                    )
                trade_log.append(
                    {
                        "side": "long" if position == 1 else "short",
                        "entry_ts": entry_ts,
                        "entry_price": entry_price,
                        "exit_ts": ts,
                        "exit_price": price,
                        "entry_equity": entry_equity,
                        "exit_equity": exit_equity,
                        "pnl": pnl,
                        "return_pct": (exit_equity / entry_equity - 1.0) * 100.0,
                        "reason": reason,
                        "signal": signal.signal_type.value,
                    }
                )
                equity = exit_equity
                position = 0
                entry_price = None
                entry_equity = None
                entry_ts = None
                position_qty = None

            def open_position(new_side: int) -> None:
                nonlocal equity, position, entry_price, entry_equity, entry_ts, position_qty
                fee = equity * self.fee_rate
                equity -= fee
                position = new_side
                entry_price = price
                entry_equity = equity
                entry_ts = ts
                position_qty = equity / price if price else 0.0
                if recorder is not None:
                    side = "buy" if new_side == 1 else "sell"
                    recorder.record_order(
                        ts,
                        side,
                        price,
                        position_qty,
                        fee,
                        None,
                    )

            if signal.signal_type == SignalType.BUY:
                if position == -1:
                    close_position("reverse_to_long")
                if position == 0:
                    open_position(1)
            elif signal.signal_type == SignalType.SELL:
                if position == 1:
                    close_position("reverse_to_short")
                if position == 0:
                    open_position(-1)
            elif signal.signal_type == SignalType.CLOSE_LONG and position == 1:
                close_position("close_long")
            elif signal.signal_type == SignalType.CLOSE_SHORT and position == -1:
                close_position("close_short")

            if position == 0 or entry_price is None or entry_equity is None:
                mark_equity = equity
            elif position == 1:
                mark_equity = entry_equity * (price / entry_price)
            else:
                mark_equity = entry_equity * (entry_price / price)

            equity_curve.append({"timestamp": ts, "equity": mark_equity})

        if position != 0 and entry_price is not None:
            last_row = candles.iloc[-1]
            price = float(last_row["close"])
            ts = int(last_row["timestamp"])
            if position == 1:
                gross_equity = entry_equity * (price / entry_price)
            else:
                gross_equity = entry_equity * (entry_price / price)
            fee = gross_equity * self.fee_rate
            exit_equity = gross_equity - fee
            pnl = exit_equity - entry_equity
            if recorder is not None:
                side = "sell" if position == 1 else "buy"
                recorder.record_order(
                    ts,
                    side,
                    price,
                    position_qty or 0.0,
                    fee,
                    pnl,
                )
            trade_log.append(
                {
                    "side": "long" if position == 1 else "short",
                    "entry_ts": entry_ts,
                    "entry_price": entry_price,
                    "exit_ts": ts,
                    "exit_price": price,
                    "entry_equity": entry_equity,
                    "exit_equity": exit_equity,
                    "pnl": pnl,
                    "return_pct": (exit_equity / entry_equity - 1.0) * 100.0,
                    "reason": "final_close",
                    "signal": "final_close",
                }
            )
            equity = exit_equity
            equity_curve[-1]["equity"] = equity

        return {
            "trade_log": trade_log,
            "equity_curve": equity_curve,
            "final_equity": equity,
        }


def compute_metrics(results: Dict, initial_capital: float) -> Dict[str, float]:
    equity_series = [point["equity"] for point in results["equity_curve"]]
    if not equity_series:
        return {
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": 0.0,
            "profitable_trades": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
        }
    peak = equity_series[0]
    max_dd = 0.0
    for value in equity_series:
        peak = max(peak, value)
        drawdown = (value - peak) / peak if peak else 0.0
        max_dd = min(max_dd, drawdown)
    trades = results["trade_log"]
    wins = len([t for t in trades if t["pnl"] > 0])
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    total_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    total_loss = abs(sum(losses)) if losses else 0.0
    total_return_pct = (equity_series[-1] / initial_capital - 1.0) * 100.0
    win_rate = (wins / len(trades) * 100.0) if trades else 0.0
    profit_factor = None
    if total_loss > 0:
        profit_factor = total_profit / total_loss
    return {
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": abs(max_dd) * 100.0,
        "total_trades": len(trades),
        "profitable_trades": wins,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest MVP (StrategyLibrary).")
    parser.add_argument(
        "--symbol",
        default=settings.okx_default_symbol,
        help="Symbol, e.g. BTC/USDT:USDT",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        help="Timeframe, e.g. 1h or 4h",
    )
    parser.add_argument(
        "--strategy",
        default="ema_trend",
        help="Strategy key (ema_trend, bollinger_range, funding_rate_arbitrage).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2000,
        help="Number of candles to backtest.",
    )
    parser.add_argument(
        "--signal-window",
        type=int,
        default=300,
        help="Lookback window used by the strategy per signal.",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="Initial capital in USDT.",
    )
    parser.add_argument(
        "--fee-rate",
        type=float,
        default=0.0005,
        help="Fee rate per trade (0.0005 = 0.05%).",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Optional backtest session name (stored in backtest_configs).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = DataService()
    candles = service.get_ohlcv(args.symbol, args.timeframe, limit=args.limit)
    if candles.empty:
        print("No candles loaded. Check symbol/timeframe or ingestion.")
        return

    funding_history = service.get_funding_history(args.symbol, limit=args.limit)
    backtest_data = BacktestDataService(candles, funding=funding_history)
    library = StrategyLibrary(backtest_data)
    strategy = library.build(args.strategy, args.symbol, args.timeframe, params=None)
    strategy.data_limit = min(args.signal_window, len(candles))

    start_ts = int(candles.iloc[0]["timestamp"])
    end_ts = int(candles.iloc[-1]["timestamp"])
    session_name = args.name or f"{args.strategy}_{args.timeframe}_{utc_now_s()}"
    recorder = BacktestRecorder(
        name=session_name,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        initial_capital=args.initial_capital,
        fee_rate=args.fee_rate,
        strategy_payload={
            "strategy_key": args.strategy,
            "strategy_params": strategy.params,
            "signal_window": args.signal_window,
        },
    )

    backtester = SimpleBacktester(
        initial_capital=args.initial_capital, fee_rate=args.fee_rate
    )
    try:
        results = backtester.run(candles, strategy, backtest_data, recorder=recorder)
        metrics = compute_metrics(results, args.initial_capital)
        recorder.finalize(results, metrics)
    finally:
        recorder.close()

    print("Backtest Summary")
    print(f"Symbol: {args.symbol} | Timeframe: {args.timeframe}")
    print(f"Strategy: {args.strategy}")
    print(f"Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"Total Trades: {metrics['total_trades']}")
    print(f"Win Rate: {metrics['win_rate_pct']:.2f}%")
    print(f"Backtest ID: {recorder.backtest_id} (config {recorder.config_id})")

    if results["trade_log"]:
        last_trade = results["trade_log"][-1]
        print("Last Trade:", last_trade)


if __name__ == "__main__":
    main()
