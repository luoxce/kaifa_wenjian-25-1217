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

export interface DataCoverageRow {
  timeframe: string;
  start_ts: number | null;
  end_ts: number | null;
  bars: number;
  expected_bars_estimate: number;
  missing_bars_estimate: number;
  last_updated_at: number | null;
}

export interface CandleIntegrityEvent {
  id: number;
  symbol: string;
  timeframe: string;
  event_type: "GAP" | "DUPLICATE" | "REPAIR";
  start_ts: number | null;
  end_ts: number | null;
  expected_bars: number | null;
  actual_bars: number | null;
  missing_bars: number | null;
  duplicate_bars: number | null;
  severity: "LOW" | "MEDIUM" | "HIGH" | string;
  detected_at: number;
  repair_job_id?: string | null;
  details_json?: string | null;
}

export interface CandleRepairJob {
  job_id: string;
  created_at: number;
  symbol: string;
  timeframe: string;
  range_start_ts: number;
  range_end_ts: number;
  status: "PENDING" | "RUNNING" | "DONE" | "FAILED" | string;
  message?: string | null;
  repaired_bars?: number | null;
  raw_payload?: string | null;
}

export type BacktestTimeframe = "15m" | "1h" | "4h" | "1d" | string;

export interface BacktestRequest {
  symbol: string;
  timeframe: BacktestTimeframe;
  startTime: string;
  endTime: string;
  initialCapital: number;
  leverage?: number;
  feeRate: number;
  slippageBps: number;
  slippageModel: "fixed" | "volatility" | "sizeImpact";
  orderSizeMode: "fixedQty" | "fixedNotional" | "percentEquity";
  orderSizeValue: number;
  allowShort: boolean;
  fundingEnabled: boolean;
  risk: {
    maxDrawdown?: number;
    maxPosition?: number;
  };
  strategyParams: Record<string, unknown>;
}

export interface BacktestSummary {
  totalReturn: number;
  cagr: number;
  mdd: number;
  maxDrawdownDuration: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  winRate: number;
  payoffRatio: number;
  profitFactor: number;
  tradesCount: number;
  fundingPnl: number;
  fundingPnlRatio: number;
}

export interface BacktestDetails {
  returns: Record<string, number | null>;
  risk: Record<string, number | null>;
  trades: Record<string, number | null>;
  costs: Record<string, number | null>;
  exposure: Record<string, number | null>;
  benchmark: Record<string, number | null>;
}

export interface BacktestEquityPoint {
  t: string;
  equity: number;
  drawdown: number;
}

export interface BacktestTrade {
  id: string;
  entryTime: string;
  exitTime: string;
  side: "long" | "short";
  entryPrice: number;
  exitPrice: number;
  qty: number;
  pnl: number;
  pnlPct: number;
  fee: number;
  funding: number;
  slippage: number;
  durationSec: number;
  reason?: string;
}

export interface BacktestResponse {
  runId: string;
  summary: BacktestSummary;
  details: BacktestDetails;
  equityCurve: BacktestEquityPoint[];
  trades: BacktestTrade[];
  positions?: Array<{ t: string; position: number; notional: number; leverage: number }>;
  logs?: string[];
}

export interface BacktestRun {
  id: number;
  runId?: string;
  name?: string;
  symbol: string;
  timeframe: BacktestTimeframe;
  createdAt: number;
  startTs?: number;
  endTs?: number;
  params?: Record<string, unknown>;
  summary: BacktestSummary;
  details: BacktestDetails;
  equityCurve: BacktestEquityPoint[];
  trades: BacktestTrade[];
  positions?: Array<{ t: string; position: number; notional: number; leverage: number }>;
  logs?: string[];
}
