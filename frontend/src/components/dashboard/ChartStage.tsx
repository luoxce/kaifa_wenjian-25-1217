import type { Candle, Order } from "@/types/schema";

import PriceChart from "@/components/PriceChart";

interface ChartStageProps {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  orders: Order[];
}

export default function ChartStage({
  symbol,
  timeframe,
  candles,
  orders,
}: ChartStageProps) {
  const lastClose = candles[candles.length - 1]?.close ?? 0;
  return (
    <section className="flex h-full flex-col rounded-lg border border-[#27272a] bg-[#0a0a0a]/80">
      <div className="flex items-center justify-between border-b border-[#27272a] px-3 py-2 text-xs text-slate-400">
        <div className="font-mono text-slate-200">
          {symbol} <span className="text-slate-500">{timeframe}</span>
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

