import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Order, Position, Trade } from "@/types/schema";

import OrdersTable from "@/components/dashboard/OrdersTable";
import PositionsTable from "@/components/dashboard/PositionsTable";
import TradesTable from "@/components/dashboard/TradesTable";
import BacktestPanel from "@/components/BacktestPanel";
import DataOpsPanel from "@/components/DataOpsPanel";

interface ExecutionDeckProps {
  positions: Position[];
  orders: Order[];
  trades: Trade[];
  symbol: string;
}

export default function ExecutionDeck({
  positions,
  orders,
  trades,
  symbol,
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
        <TabsContent value="positions" className="mt-3">
          <PositionsTable positions={positions} />
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
