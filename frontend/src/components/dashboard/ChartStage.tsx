import type { Candle, Order } from "@/types/schema";
import { TIMEFRAMES } from "@/lib/constants";

import PriceChart from "@/components/PriceChart";

interface ChartStageProps {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  orders: Order[];
  onTimeframeChange?: (timeframe: string) => void;
  timeframeOptions?: string[];
}

export default function ChartStage({
  symbol,
  timeframe,
  candles,
  orders,
  onTimeframeChange,
  timeframeOptions,
}: ChartStageProps) {
  const lastClose = candles[candles.length - 1]?.close ?? 0;
  const options = timeframeOptions ?? TIMEFRAMES;
  return (
    <section className="flex h-full flex-col rounded-lg border border-[#27272a] bg-[#0a0a0a]/80">
      <div className="flex items-center justify-between border-b border-[#27272a] px-3 py-2 text-xs text-slate-400">
        <div className="font-mono text-slate-200">
          {symbol}{" "}
          <span className="ml-2 text-slate-500">{timeframe}</span>
          {onTimeframeChange && (
            <select
              className="ml-3 rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px] text-slate-200"
              value={timeframe}
              onChange={(event) => onTimeframeChange(event.target.value)}
            >
              {options.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="font-mono">
          Last Close:{" "}
          <span className="text-slate-200">{lastClose.toFixed(2)}</span>
        </div>
      </div>
      <div className="flex-1">
        <PriceChart candles={candles} orders={orders} />
      </div>
    </section>
  );
}
