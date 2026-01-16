import type {
  BacktestDetails,
  BacktestEquityPoint,
  BacktestSummary,
  BacktestTrade,
} from "@/types/schema";

type RawEquityPoint = { timestamp?: number; time?: number; equity?: number; value?: number };
type RawTrade = Record<string, unknown>;

const toNumber = (value: unknown, fallback = 0): number => {
  if (value === null || value === undefined) return fallback;
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
};

const toIso = (ts: number) => new Date(ts).toISOString();

const safeJson = <T>(value: unknown, fallback: T): T => {
  if (!value) return fallback;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as T;
    } catch {
      return fallback;
    }
  }
  return value as T;
};

export const parseEquityCurve = (raw: unknown): BacktestEquityPoint[] => {
  const points = safeJson<RawEquityPoint[]>(raw, []);
  if (!Array.isArray(points)) return [];
  let peak = 0;
  return points
    .map((point) => {
      const ts = toNumber(point.timestamp ?? point.time, 0);
      const equity = toNumber(point.equity ?? point.value, 0);
      peak = Math.max(peak, equity);
      const drawdown = peak > 0 ? (equity - peak) / peak : 0;
      return {
        t: ts ? toIso(ts) : "",
        equity,
        drawdown,
      };
    })
    .filter((point) => point.t);
};

export const parseTrades = (raw: unknown): BacktestTrade[] => {
  const trades = safeJson<RawTrade[]>(raw, []);
  if (!Array.isArray(trades)) return [];
  return trades.map((trade, idx) => {
    const entryTs = toNumber(trade.entry_ts, 0);
    const exitTs = toNumber(trade.exit_ts, 0);
    const entryPrice = toNumber(trade.entry_price, 0);
    const exitPrice = toNumber(trade.exit_price, 0);
    const entryEquity = toNumber(trade.entry_equity, 0);
    const exitEquity = toNumber(trade.exit_equity, 0);
    const pnl = toNumber(trade.pnl, 0);
    const pnlPct = toNumber(trade.return_pct, 0);
    return {
      id: `${idx + 1}`,
      entryTime: entryTs ? toIso(entryTs) : "",
      exitTime: exitTs ? toIso(exitTs) : "",
      side: (trade.side as "long" | "short") || "long",
      entryPrice,
      exitPrice,
      qty: entryPrice ? entryEquity / entryPrice : 0,
      pnl,
      pnlPct,
      fee: 0,
      funding: 0,
      slippage: 0,
      durationSec: entryTs && exitTs ? Math.max(exitTs - entryTs, 0) / 1000 : 0,
      reason: typeof trade.reason === "string" ? trade.reason : undefined,
    };
  });
};

const computeReturns = (equityCurve: BacktestEquityPoint[]) => {
  const returns: number[] = [];
  for (let i = 1; i < equityCurve.length; i += 1) {
    const prev = equityCurve[i - 1].equity;
    const curr = equityCurve[i].equity;
    if (prev > 0) {
      returns.push((curr - prev) / prev);
    }
  }
  return returns;
};

const mean = (values: number[]) =>
  values.length ? values.reduce((acc, val) => acc + val, 0) / values.length : 0;

const std = (values: number[]) => {
  if (values.length < 2) return 0;
  const avg = mean(values);
  const variance =
    values.reduce((acc, val) => acc + (val - avg) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
};

const percentile = (values: number[], p: number) => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.max(0, Math.min(sorted.length - 1, Math.floor(sorted.length * p)));
  return sorted[idx];
};

const timeframeToAnnualization = (timeframe: string) => {
  switch (timeframe) {
    case "15m":
      return 24 * 4 * 365;
    case "1h":
      return 24 * 365;
    case "4h":
      return 6 * 365;
    case "1d":
      return 365;
    default:
      return 365;
  }
};

const computeDrawdownDuration = (equityCurve: BacktestEquityPoint[]) => {
  let peak = -Infinity;
  let peakTime = "";
  let maxDuration = 0;
  for (const point of equityCurve) {
    if (point.equity >= peak) {
      peak = point.equity;
      peakTime = point.t;
    } else if (peakTime) {
      const duration = new Date(point.t).getTime() - new Date(peakTime).getTime();
      maxDuration = Math.max(maxDuration, duration);
    }
  }
  return maxDuration / 1000;
};

export const buildSummary = ({
  equityCurve,
  trades,
  initialCapital,
  timeframe,
  metrics,
}: {
  equityCurve: BacktestEquityPoint[];
  trades: BacktestTrade[];
  initialCapital: number;
  timeframe: string;
  metrics?: Record<string, unknown>;
}): BacktestSummary => {
  const finalEquity = equityCurve[equityCurve.length - 1]?.equity ?? initialCapital;
  const totalReturn =
    metrics && "total_return_pct" in metrics
      ? toNumber(metrics.total_return_pct)
      : initialCapital > 0
      ? (finalEquity / initialCapital - 1) * 100
      : 0;
  const mdd =
    metrics && "max_drawdown_pct" in metrics
      ? toNumber(metrics.max_drawdown_pct)
      : Math.abs(
          equityCurve.reduce((min, point) => Math.min(min, point.drawdown), 0) * 100
        );
  const winRate =
    metrics && "win_rate_pct" in metrics
      ? toNumber(metrics.win_rate_pct)
      : trades.length
      ? (trades.filter((trade) => trade.pnl > 0).length / trades.length) * 100
      : 0;
  const profitFactor =
    metrics && "profit_factor" in metrics
      ? toNumber(metrics.profit_factor)
      : computeProfitFactor(trades);
  const years = computeYears(equityCurve);
  const cagr = years > 0 ? ((finalEquity / initialCapital) ** (1 / years) - 1) * 100 : 0;
  const returns = computeReturns(equityCurve);
  const annualization = timeframeToAnnualization(timeframe);
  const sharpe = returns.length ? (mean(returns) / std(returns)) * Math.sqrt(annualization) : 0;
  const downside = returns.filter((value) => value < 0);
  const sortino =
    downside.length > 1 ? (mean(returns) / std(downside)) * Math.sqrt(annualization) : 0;
  const maxDrawdownDuration = computeDrawdownDuration(equityCurve);
  const calmar = mdd > 0 ? cagr / mdd : 0;
  const payoffRatio = computePayoffRatio(trades);

  return {
    totalReturn,
    cagr,
    mdd,
    maxDrawdownDuration,
    sharpe,
    sortino,
    calmar,
    winRate,
    payoffRatio,
    profitFactor,
    tradesCount: trades.length,
    fundingPnl: 0,
    fundingPnlRatio: 0,
  };
};

export const buildDetails = ({
  equityCurve,
  trades,
  timeframe,
  benchmarkReturn,
  strategyReturn,
  initialCapital,
}: {
  equityCurve: BacktestEquityPoint[];
  trades: BacktestTrade[];
  timeframe: string;
  benchmarkReturn: number | null;
  strategyReturn: number;
  initialCapital: number;
}): BacktestDetails => {
  const returns = computeReturns(equityCurve);
  const annualization = timeframeToAnnualization(timeframe);
  const monthly = computeMonthlyReturns(equityCurve);
  const daily = computeDailyReturns(equityCurve);
  const totalProfit = trades.filter((t) => t.pnl > 0).reduce((acc, t) => acc + t.pnl, 0);
  const totalLoss = Math.abs(trades.filter((t) => t.pnl < 0).reduce((acc, t) => acc + t.pnl, 0));
  const grossProfit = totalProfit + totalLoss;

  return {
    returns: {
      monthlyReturnMean: monthly.length ? mean(monthly) * 100 : null,
      monthlyReturnStd: monthly.length ? std(monthly) * 100 : null,
      bestDay: daily.length ? Math.max(...daily) * 100 : null,
      worstDay: daily.length ? Math.min(...daily) * 100 : null,
      skew: daily.length ? skewness(daily) : null,
      kurtosis: daily.length ? kurtosis(daily) : null,
    },
    risk: {
      volatility: returns.length ? std(returns) * Math.sqrt(annualization) * 100 : null,
      downsideVolatility: returns.length
        ? std(returns.filter((value) => value < 0)) * Math.sqrt(annualization) * 100
        : null,
      var95: returns.length ? percentile(returns, 0.05) * 100 : null,
      cvar95: returns.length ? mean(returns.filter((value) => value <= percentile(returns, 0.05))) * 100 : null,
      maxDailyDrawdown: computeMaxDailyDrawdown(equityCurve) * 100,
    },
    trades: {
      avgTradePnl: trades.length ? mean(trades.map((t) => t.pnl)) : null,
      expectancy: trades.length
        ? mean(trades.map((t) => (t.pnl / (initialCapital || 1)) * 100))
        : null,
      maxLosingStreak: computeMaxLosingStreak(trades),
      avgHoldingTime: trades.length ? mean(trades.map((t) => t.durationSec)) : null,
      turnoverPerDay: computeTradesPerDay(trades, equityCurve),
    },
    costs: {
      feePaid: 0,
      slippageCost: 0,
      costDrag: grossProfit > 0 ? (0 / grossProfit) * 100 : null,
      avgCostPerTrade: trades.length ? 0 : null,
    },
    exposure: {
      maxExposure: null,
      avgLeverage: null,
      maxMarginUsage: null,
      liquidationCount: 0,
    },
    benchmark: {
      alphaVsBtc:
        benchmarkReturn !== null ? strategyReturn - benchmarkReturn : null,
      strategyMddVsBenchmark: null,
      informationRatio: null,
    },
  };
};

const computeProfitFactor = (trades: BacktestTrade[]) => {
  const profit = trades.filter((t) => t.pnl > 0).reduce((acc, t) => acc + t.pnl, 0);
  const loss = Math.abs(trades.filter((t) => t.pnl < 0).reduce((acc, t) => acc + t.pnl, 0));
  if (!loss) return 0;
  return profit / loss;
};

const computePayoffRatio = (trades: BacktestTrade[]) => {
  const wins = trades.filter((t) => t.pnl > 0).map((t) => t.pnl);
  const losses = trades.filter((t) => t.pnl < 0).map((t) => Math.abs(t.pnl));
  if (!wins.length || !losses.length) return 0;
  return mean(wins) / mean(losses);
};

const computeYears = (equityCurve: BacktestEquityPoint[]) => {
  if (equityCurve.length < 2) return 0;
  const start = new Date(equityCurve[0].t).getTime();
  const end = new Date(equityCurve[equityCurve.length - 1].t).getTime();
  if (!start || !end || end <= start) return 0;
  return (end - start) / (365 * 24 * 60 * 60 * 1000);
};

const computeMonthlyReturns = (equityCurve: BacktestEquityPoint[]) => {
  const byMonth: Record<string, number> = {};
  for (const point of equityCurve) {
    const date = new Date(point.t);
    const key = `${date.getUTCFullYear()}-${date.getUTCMonth() + 1}`;
    byMonth[key] = point.equity;
  }
  const monthKeys = Object.keys(byMonth).sort();
  const returns: number[] = [];
  for (let i = 1; i < monthKeys.length; i += 1) {
    const prev = byMonth[monthKeys[i - 1]];
    const curr = byMonth[monthKeys[i]];
    if (prev) returns.push((curr - prev) / prev);
  }
  return returns;
};

const computeDailyReturns = (equityCurve: BacktestEquityPoint[]) => {
  const byDay: Record<string, number> = {};
  for (const point of equityCurve) {
    const date = new Date(point.t);
    const key = `${date.getUTCFullYear()}-${date.getUTCMonth() + 1}-${date.getUTCDate()}`;
    byDay[key] = point.equity;
  }
  const dayKeys = Object.keys(byDay).sort();
  const returns: number[] = [];
  for (let i = 1; i < dayKeys.length; i += 1) {
    const prev = byDay[dayKeys[i - 1]];
    const curr = byDay[dayKeys[i]];
    if (prev) returns.push((curr - prev) / prev);
  }
  return returns;
};

const computeMaxDailyDrawdown = (equityCurve: BacktestEquityPoint[]) => {
  const daily = computeDailyReturns(equityCurve);
  if (!daily.length) return 0;
  let max = 0;
  for (const value of daily) {
    max = Math.min(max, value);
  }
  return Math.abs(max);
};

const computeMaxLosingStreak = (trades: BacktestTrade[]) => {
  let streak = 0;
  let maxStreak = 0;
  for (const trade of trades) {
    if (trade.pnl < 0) {
      streak += 1;
      maxStreak = Math.max(maxStreak, streak);
    } else {
      streak = 0;
    }
  }
  return maxStreak;
};

const computeTradesPerDay = (trades: BacktestTrade[], equityCurve: BacktestEquityPoint[]) => {
  if (!trades.length || equityCurve.length < 2) return 0;
  const days = computeYears(equityCurve) * 365;
  return days > 0 ? trades.length / days : 0;
};

const skewness = (values: number[]) => {
  if (values.length < 3) return 0;
  const avg = mean(values);
  const s = std(values);
  if (s === 0) return 0;
  const n = values.length;
  const m3 = values.reduce((acc, val) => acc + (val - avg) ** 3, 0) / n;
  return m3 / s ** 3;
};

const kurtosis = (values: number[]) => {
  if (values.length < 4) return 0;
  const avg = mean(values);
  const s = std(values);
  if (s === 0) return 0;
  const n = values.length;
  const m4 = values.reduce((acc, val) => acc + (val - avg) ** 4, 0) / n;
  return m4 / s ** 4 - 3;
};
