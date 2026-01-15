export interface SystemHealth {
  status: "ok" | "degraded" | "down";
  latency_ms: number;
  last_sync_time: number;
  trading_enabled: boolean;
}

export interface AccountBalance {
  asset: string;
  free: number;
  used: number;
  total: number;
}

export interface AccountSummary {
  total_equity: number;
  unrealized_pnl: number;
  daily_pnl: number;
  balances: AccountBalance[];
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Order {
  order_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  status: "NEW" | "PARTIALLY_FILLED" | "FILLED" | "CANCELED" | "REJECTED";
  price: number;
  filled_amount: number;
  timestamp: number;
}

export interface Position {
  symbol: string;
  side: "long" | "short";
  size: number;
  entry_price: number;
  mark_price: number;
  unrealized_pnl: number;
}

export interface StrategyDecision {
  timestamp: number;
  strategy_name: string;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  reasoning: string;
}
