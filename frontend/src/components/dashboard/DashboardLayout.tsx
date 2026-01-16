import { useState } from "react";

import HeaderBar from "@/components/dashboard/HeaderBar";
import ChartStage from "@/components/dashboard/ChartStage";
import DecisionStream from "@/components/dashboard/DecisionStream";
import ExecutionDeck from "@/components/dashboard/ExecutionDeck";
import { useMarketData } from "@/hooks/useMarketData";

const defaultSymbol =
  (import.meta.env.VITE_DASHBOARD_SYMBOL as string | undefined) ??
  "BTC/USDT:USDT";
const defaultTimeframe =
  (import.meta.env.VITE_DASHBOARD_TIMEFRAME as string | undefined) ?? "15m";
const allowedTimeframes = ["15m", "1h", "1d"];
const defaultLimitRaw = import.meta.env.VITE_DASHBOARD_LIMIT as
  | string
  | undefined;
const defaultLimit = Number.isFinite(Number(defaultLimitRaw))
  ? Number(defaultLimitRaw)
  : 200;

export default function DashboardLayout() {
  const initialTimeframe = allowedTimeframes.includes(defaultTimeframe)
    ? defaultTimeframe
    : "15m";
  const [timeframe, setTimeframe] = useState(initialTimeframe);
  const { data, isLoading } = useMarketData({
    symbol: defaultSymbol,
    timeframe,
    limit: defaultLimit,
  });

  if (isLoading || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050505] text-slate-400">
        Loading dashboard...
      </div>
    );
  }

  const { health, candles, orders, positions, decisions } = data;
  return (
    <div className="min-h-screen bg-[#050505] text-slate-100">
      <div className="grid h-screen grid-cols-[minmax(0,7fr)_minmax(0,3fr)] grid-rows-[48px_minmax(0,1fr)_minmax(0,0.55fr)] gap-3 p-3">
        <div className="col-span-2">
          <HeaderBar health={health} />
        </div>
        <div className="col-start-1 row-start-2">
          <ChartStage
            symbol={defaultSymbol}
            timeframe={timeframe}
            candles={candles}
            orders={orders}
            onTimeframeChange={setTimeframe}
            timeframeOptions={allowedTimeframes}
          />
        </div>
        <div className="col-start-2 row-start-2 row-span-2">
          <DecisionStream decisions={decisions} />
        </div>
        <div className="col-start-1 row-start-3">
          <ExecutionDeck positions={positions} orders={orders} />
        </div>
      </div>
    </div>
  );
}
