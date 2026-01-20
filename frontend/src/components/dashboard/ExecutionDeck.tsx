import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AccountSummary, Order, Position, Trade } from "@/types/schema";

import OrdersTable from "@/components/dashboard/OrdersTable";
import PositionsTable from "@/components/dashboard/PositionsTable";
import TradesTable from "@/components/dashboard/TradesTable";
import BacktestPanel from "@/components/BacktestPanel";
import DataOpsPanel from "@/components/DataOpsPanel";
import AccountPanel from "@/components/dashboard/AccountPanel";

interface ExecutionDeckProps {
  account: AccountSummary;
  positions: Position[];
  orders: Order[];
  trades: Trade[];
  symbol: string;
  lastPrice?: number;
}

export default function ExecutionDeck({
  account,
  positions,
  orders,
  trades,
  symbol,
  lastPrice,
}: ExecutionDeckProps) {
  return (
    <section className="flex h-full flex-col rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-3">
      <Tabs defaultValue="positions" className="h-full">
        <TabsList>
          <TabsTrigger value="positions">Positions</TabsTrigger>
          <TabsTrigger value="orders">Open Orders</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="backtest">Backtest</TabsTrigger>
          <TabsTrigger value="dataops">Data Ops</TabsTrigger>
        </TabsList>
        <TabsContent value="positions" className="mt-3 h-full">
          <div className="flex h-full flex-col gap-3 overflow-hidden">
            <AccountPanel
              account={account}
              positions={positions}
              symbol={symbol}
              lastPrice={lastPrice}
            />
            <div className="flex-1 overflow-y-auto pr-1">
              <div className="rounded-md border border-[#1f1f1f] bg-[#050505]/70 p-2">
                <div className="mb-2 text-[11px] text-slate-400">
                  Open Positions
                </div>
                <PositionsTable positions={positions} />
              </div>
            </div>
          </div>
        </TabsContent>
        <TabsContent value="orders" className="mt-3">
          <OrdersTable orders={orders} />
        </TabsContent>
        <TabsContent value="history" className="mt-3">
          <TradesTable trades={trades} />
        </TabsContent>
        <TabsContent value="backtest" className="mt-3">
          <BacktestPanel />
        </TabsContent>
        <TabsContent value="dataops" className="mt-3">
          <DataOpsPanel defaultSymbol={symbol} />
        </TabsContent>
      </Tabs>
    </section>
  );
}
