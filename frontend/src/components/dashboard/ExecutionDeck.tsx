import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Order, Position } from "@/types/schema";

import OrdersTable from "@/components/dashboard/OrdersTable";
import PositionsTable from "@/components/dashboard/PositionsTable";
import BacktestPanel from "@/components/BacktestPanel";
import DataOpsPanel from "@/components/DataOpsPanel";

interface ExecutionDeckProps {
  positions: Position[];
  orders: Order[];
}

export default function ExecutionDeck({ positions, orders }: ExecutionDeckProps) {
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
        <TabsContent value="history" className="mt-3 text-xs text-slate-500">
          Trade history coming soon.
        </TabsContent>
        <TabsContent value="backtest" className="mt-3">
          <BacktestPanel />
        </TabsContent>
        <TabsContent value="dataops" className="mt-3">
          <DataOpsPanel />
        </TabsContent>
      </Tabs>
    </section>
  );
}

