import type { Candle, Order } from "@/types/schema";
import { TIMEFRAMES } from "@/lib/constants";

import PriceChart from "@/components/PriceChart";

interface ChartStageProps {
  symbol: string;
  timeframe: string;
  candles: Candle[];
  orders: Order[];
  symbolOptions?: string[];
  onTimeframeChange?: (timeframe: string) => void;
  timeframeOptions?: string[];
  onSymbolChange?: (symbol: string) => void;
  limit?: number;
  onLimitChange?: (limit: number) => void;
}

export default function ChartStage({
  symbol,
  timeframe,
  candles,
  orders,
  symbolOptions,
  onTimeframeChange,
  timeframeOptions,
  onSymbolChange,
  limit,
  onLimitChange,
}: ChartStageProps) {
  const lastClose = candles[candles.length - 1]?.close ?? 0;
  const options = timeframeOptions ?? TIMEFRAMES;
  return (
    <section className="flex h-full flex-col rounded-lg border border-[#27272a] bg-[#0a0a0a]/80">
      <div className="flex items-center justify-between border-b border-[#27272a] px-3 py-2 text-xs text-slate-400">
        <div className="font-mono text-slate-200">
          {onSymbolChange ? (
            symbolOptions && symbolOptions.length ? (
              <select
                className="rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px] text-slate-200"
                value={symbol}
                onChange={(event) => onSymbolChange(event.target.value)}
              >
                {symbolOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px] text-slate-200"
                value={symbol}
                onChange={(event) => onSymbolChange(event.target.value)}
              />
            )
          ) : (
            <span>{symbol}</span>
          )}{" "}
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
          {onLimitChange && (
            <label className="ml-3 inline-flex items-center gap-2 text-[10px] text-slate-500">
              Bars
              <input
                className="w-20 rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px] text-slate-200"
                value={limit ?? ""}
                onChange={(event) => onLimitChange(Number(event.target.value))}
                type="number"
                min={50}
                max={5000}
              />
            </label>
          )}
        </div>
        <div className="font-mono">
          Last Close:{" "}
          <span className="text-slate-200">{lastClose.toFixed(2)}</span>
        </div>
      </div>
      <div className="flex-1">
        {candles.length ? (
          <PriceChart candles={candles} orders={orders} />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No candles loaded. Run ingest or adjust symbol/timeframe.
          </div>
        )}
      </div>
    </section>
  );
}
