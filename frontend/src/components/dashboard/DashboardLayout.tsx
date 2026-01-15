import type { MarketDataSnapshot } from "@/hooks/useMarketData";

import HeaderBar from "@/components/dashboard/HeaderBar";
import ChartStage from "@/components/dashboard/ChartStage";
import DecisionStream from "@/components/dashboard/DecisionStream";
import ExecutionDeck from "@/components/dashboard/ExecutionDeck";

interface DashboardLayoutProps {
  data: MarketDataSnapshot;
}

export default function DashboardLayout({ data }: DashboardLayoutProps) {
  const { health, candles, orders, positions, decisions } = data;
  return (
    <div className="min-h-screen bg-[#050505] text-slate-100">
      <div className="grid h-screen grid-cols-[minmax(0,7fr)_minmax(0,3fr)] grid-rows-[48px_minmax(0,1fr)_minmax(0,0.55fr)] gap-3 p-3">
        <div className="col-span-2">
          <HeaderBar health={health} />
        </div>
        <div className="col-start-1 row-start-2">
          <ChartStage
            symbol="BTC/USDT:USDT"
            timeframe="15m"
            candles={candles}
            orders={orders}
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

