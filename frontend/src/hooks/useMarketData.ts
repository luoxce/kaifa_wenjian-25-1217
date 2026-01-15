import { useQuery } from "@tanstack/react-query";

import type {
  AccountSummary,
  Candle,
  Order,
  Position,
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
}

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const rand = (min: number, max: number) =>
  Math.random() * (max - min) + min;

let mockCache: MarketDataSnapshot | null = null;

const mockCandles = (points = 120): Candle[] => {
  const data: Candle[] = [];
  let lastClose = 64000 + rand(-500, 500);
  const now = Math.floor(Date.now() / 1000);
  for (let i = points - 1; i >= 0; i -= 1) {
    const time = now - i * 60 * 15;
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

const mockSnapshot = (): MarketDataSnapshot => {
  if (!mockCache) {
    const candles = mockCandles(160);
    const last = candles[candles.length - 1];
    mockCache = {
      health: {
        status: "ok",
        latency_ms: Math.round(rand(40, 120)),
        last_sync_time: Date.now(),
        trading_enabled: true,
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
          symbol: "BTC/USDT:USDT",
          side: "BUY",
          status: "FILLED",
          price: last.close - 120,
          filled_amount: 0.02,
          timestamp: last.time - 300,
        },
        {
          order_id: "ord-102",
          symbol: "BTC/USDT:USDT",
          side: "SELL",
          status: "NEW",
          price: last.close + 180,
          filled_amount: 0.0,
          timestamp: last.time - 120,
        },
      ],
      positions: [
        {
          symbol: "BTC/USDT:USDT",
          side: "long",
          size: 0.05,
          entry_price: last.close - 320,
          mark_price: last.close,
          unrealized_pnl: 42.6,
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
    };
  }
  return {
    ...mockCache,
    health: {
      ...mockCache.health,
      latency_ms: Math.round(rand(40, 120)),
      last_sync_time: Date.now(),
    },
  };
};

const fetchSnapshot = async (): Promise<MarketDataSnapshot> => {
  if (!apiBase) {
    return mockSnapshot();
  }
  try {
    const health = await fetch(`${apiBase}/api/health`).then((r) => r.json());
    const candles = await fetch(
      `${apiBase}/api/market/candles?symbol=BTC/USDT:USDT&timeframe=15m&limit=200`
    ).then((r) => r.json());
    const account = await fetch(`${apiBase}/api/account/summary`).then((r) =>
      r.json()
    );
    const decisions = await fetch(
      `${apiBase}/api/decisions?symbol=BTC/USDT:USDT&limit=50`
    ).then((r) => r.json());
    const orders = await fetch(
      `${apiBase}/api/orders?symbol=BTC/USDT:USDT&limit=50`
    ).then((r) => r.json());
    const positions = await fetch(
      `${apiBase}/api/positions?symbol=BTC/USDT:USDT`
    ).then((r) => r.json());

    return {
      health,
      account,
      candles: candles?.data || [],
      orders: orders?.data || [],
      positions: positions?.data || [],
      decisions: decisions?.data || [],
    };
  } catch (error) {
    return mockSnapshot();
  }
};

export const useMarketData = () =>
  useQuery({
    queryKey: ["market-data"],
    queryFn: fetchSnapshot,
    refetchInterval: 5000,
  });
