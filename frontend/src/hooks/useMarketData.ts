import { useQuery } from "@tanstack/react-query";

import type {
  AccountSummary,
  Candle,
  Order,
  Position,
  Trade,
  StrategyDecision,
  SystemHealth,
} from "@/types/schema";

export interface MarketDataSnapshot {
  health: SystemHealth;
  account: AccountSummary;
  candles: Candle[];
  orders: Order[];
  positions: Position[];
  decisions: StrategyDecision[];
  trades: Trade[];
}

export interface MarketDataOptions {
  symbol?: string;
  timeframe?: string;
  limit?: number;
}

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
const dashboardSymbol =
  (import.meta.env.VITE_DASHBOARD_SYMBOL as string | undefined) ??
  "BTC/USDT:USDT";
const dashboardTimeframe =
  (import.meta.env.VITE_DASHBOARD_TIMEFRAME as string | undefined) ?? "15m";
const dashboardLimitRaw = import.meta.env.VITE_DASHBOARD_LIMIT as
  | string
  | undefined;
const dashboardLimit = Number.isFinite(Number(dashboardLimitRaw))
  ? Number(dashboardLimitRaw)
  : 200;

const rand = (min: number, max: number) =>
  Math.random() * (max - min) + min;

const mockCache = new Map<string, MarketDataSnapshot>();

const mockCandles = (points = 120, timeframe = dashboardTimeframe): Candle[] => {
  const data: Candle[] = [];
  let lastClose = 64000 + rand(-500, 500);
  const now = Math.floor(Date.now() / 1000);
  for (let i = points - 1; i >= 0; i -= 1) {
    const time = now - i * timeframeToSeconds(timeframe);
    const open = lastClose + rand(-120, 120);
    const close = open + rand(-160, 160);
    const high = Math.max(open, close) + rand(20, 140);
    const low = Math.min(open, close) - rand(20, 140);
    const volume = Math.max(0, rand(12, 420));
    data.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
      volume: Number(volume.toFixed(2)),
    });
    lastClose = close;
  }
  return data;
};

const mockSnapshot = (
  symbol: string,
  timeframe: string,
  limit: number
): MarketDataSnapshot => {
  const key = `${symbol}-${timeframe}-${limit}`;
  if (!mockCache.has(key)) {
    const candles = mockCandles(Math.max(120, Math.min(limit, 800)), timeframe);
    const last = candles[candles.length - 1];
    mockCache.set(key, {
      health: {
        status: "ok",
        latency_ms: Math.round(rand(40, 120)),
        last_sync_time: Date.now(),
        trading_enabled: true,
        api_write_enabled: true,
        okx_is_demo: true,
        okx_default_symbol: symbol,
      },
      account: {
        total_equity: 10234.5,
        unrealized_pnl: 52.4,
        daily_pnl: -13.7,
        balances: [
          { asset: "USDT", free: 6021.2, used: 1800.8, total: 7822.0 },
          { asset: "BTC", free: 0.12, used: 0.02, total: 0.14 },
        ],
      },
      candles,
      orders: [
        {
          order_id: "ord-101",
          symbol,
          side: "BUY",
          status: "FILLED",
          price: last.close - 120,
          filled_amount: 0.02,
          timestamp: last.time - 300,
        },
        {
          order_id: "ord-102",
          symbol,
          side: "SELL",
          status: "NEW",
          price: last.close + 180,
          filled_amount: 0.0,
          timestamp: last.time - 120,
        },
      ],
      positions: [
        {
          symbol,
          side: "long",
          size: 0.05,
          entry_price: last.close - 320,
          mark_price: last.close,
          unrealized_pnl: 42.6,
        },
      ],
      trades: [
        {
          trade_id: "trade-301",
          symbol,
          side: "BUY",
          price: last.close - 80,
          amount: 0.01,
          fee: 0.02,
          timestamp: last.time - 600,
        },
      ],
      decisions: [
        {
          timestamp: Date.now() - 120000,
          strategy_name: "ema_trend",
          signal: "BUY",
          confidence: 0.72,
          reasoning: "ADX rising with higher highs, MACD histogram positive.",
        },
        {
          timestamp: Date.now() - 540000,
          strategy_name: "bollinger_range",
          signal: "HOLD",
          confidence: 0.48,
          reasoning: "Bands expanding; waiting for confirmation.",
        },
      ],
    });
  }
  const base = mockCache.get(key)!;
  return {
    ...base,
    health: {
      ...base.health,
      latency_ms: Math.round(rand(40, 120)),
      last_sync_time: Date.now(),
    },
  };
};

const fetchSnapshot = async (
  symbol: string,
  timeframe: string,
  limit: number
): Promise<MarketDataSnapshot> => {
  if (!apiBase) {
    return mockSnapshot(symbol, timeframe, limit);
  }
  try {
    const health = await fetch(`${apiBase}/api/health`).then((r) => r.json());
    const candles = await fetch(
      `${apiBase}/api/market/candles?symbol=${encodeURIComponent(
        symbol
      )}&timeframe=${timeframe}&limit=${limit}`
    ).then((r) => r.json());
    const account = await fetch(`${apiBase}/api/account/summary`).then((r) =>
      r.json()
    );
    const decisions = await fetch(
      `${apiBase}/api/decisions?symbol=${encodeURIComponent(symbol)}&limit=50`
    ).then((r) => r.json());
    const orders = await fetch(
      `${apiBase}/api/orders?symbol=${encodeURIComponent(symbol)}&limit=50`
    ).then((r) => r.json());
    const positions = await fetch(
      `${apiBase}/api/positions?symbol=${encodeURIComponent(symbol)}`
    ).then((r) => r.json());
    const trades = await fetch(
      `${apiBase}/api/trades?symbol=${encodeURIComponent(symbol)}&limit=50`
    ).then((r) => r.json());

    return {
      health,
      account,
      candles: candles?.data || [],
      orders: orders?.data || [],
      positions: positions?.data || [],
      decisions: decisions?.data || [],
      trades: trades?.data || [],
    };
  } catch (error) {
    return mockSnapshot(symbol, timeframe, limit);
  }
};

export const useMarketData = (options?: MarketDataOptions) => {
  const symbol = options?.symbol ?? dashboardSymbol;
  const timeframe = options?.timeframe ?? dashboardTimeframe;
  const limit = options?.limit ?? dashboardLimit;
  return useQuery({
    queryKey: ["market-data", symbol, timeframe, limit],
    queryFn: () => fetchSnapshot(symbol, timeframe, limit),
    refetchInterval: 5000,
  });
};

const timeframeToSeconds = (timeframe: string) => {
  if (timeframe.endsWith("m")) {
    return Number(timeframe.replace("m", "")) * 60;
  }
  if (timeframe.endsWith("h")) {
    return Number(timeframe.replace("h", "")) * 60 * 60;
  }
  if (timeframe.endsWith("d")) {
    return Number(timeframe.replace("d", "")) * 24 * 60 * 60;
  }
  return 60 * 15;
};
