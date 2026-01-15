import React from "react";
import { BadgeDollarSign, Cpu, Activity } from "lucide-react";

import type { MarketDataSnapshot } from "@/hooks/useMarketData";
import PriceChart from "@/components/PriceChart";
import PositionsTable from "@/components/PositionsTable";
import DecisionLog from "@/components/DecisionLog";
import BacktestPanel from "@/components/BacktestPanel";
import DataOpsPanel from "@/components/DataOpsPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface DashboardLayoutProps {
  data: MarketDataSnapshot;
}

const formatTs = (ts: number) =>
  new Date(ts).toLocaleString(undefined, { hour12: false });

export default function DashboardLayout({ data }: DashboardLayoutProps) {
  const { account, health, candles, orders, positions, decisions } = data;
  return (
    <div className="min-h-screen bg-slate-950 px-3 py-4 text-slate-100">
      <div className="grid grid-cols-[minmax(0,2fr)_minmax(280px,1fr)] grid-rows-[auto_1fr_auto] gap-3">
        <header className="col-span-2 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                Alpha Arena - Quant Dashboard
              </h1>
              <p className="text-xs text-slate-400">
                Real-time execution and decision telemetry
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <InfoCard
                icon={<BadgeDollarSign className="h-4 w-4 text-emerald-400" />}
                label="Total Equity"
                value={`${account.total_equity.toFixed(2)} USDT`}
                sub={`Daily: ${account.daily_pnl.toFixed(2)}`}
              />
              <InfoCard
                icon={<Activity className="h-4 w-4 text-sky-400" />}
                label="Unrealized PnL"
                value={`${account.unrealized_pnl.toFixed(2)} USDT`}
                sub={`Last Sync: ${formatTs(health.last_sync_time)}`}
              />
              <InfoCard
                icon={<Cpu className="h-4 w-4 text-amber-400" />}
                label="System Health"
                value={`${health.status.toUpperCase()} / ${health.latency_ms}ms`}
                sub={health.trading_enabled ? "Trading Enabled" : "Trading Disabled"}
              />
            </div>
          </div>
        </header>

        <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-2">
          <div className="flex items-center justify-between px-2 pb-2 text-xs text-slate-400">
            <span>BTC/USDT:USDT 15m</span>
            <span className="font-mono">
              Last Close: {candles[candles.length - 1]?.close?.toFixed(2)}
            </span>
          </div>
          <div className="h-[520px]">
            <PriceChart candles={candles} orders={orders} />
          </div>
        </section>

        <aside className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
            <span>Decision Log</span>
            <span className="font-mono">{decisions.length} entries</span>
          </div>
          <div className="max-h-[580px] overflow-y-auto pr-1">
            <DecisionLog decisions={decisions} />
          </div>
        </aside>

        <section className="col-span-2 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
          <Tabs defaultValue="positions">
            <TabsList>
              <TabsTrigger value="positions">Positions</TabsTrigger>
              <TabsTrigger value="orders">Open Orders</TabsTrigger>
              <TabsTrigger value="trades">Trade History</TabsTrigger>
              <TabsTrigger value="backtest">Backtest</TabsTrigger>
              <TabsTrigger value="dataops">Data Ops</TabsTrigger>
            </TabsList>
            <TabsContent value="positions">
              <PositionsTable positions={positions} />
            </TabsContent>
            <TabsContent value="orders">
              <OrdersTable orders={orders} />
            </TabsContent>
            <TabsContent value="trades">
              <div className="text-xs text-slate-400">Trade history coming soon.</div>
            </TabsContent>
            <TabsContent value="backtest">
              <BacktestPanel />
            </TabsContent>
            <TabsContent value="dataops">
              <DataOpsPanel />
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </div>
  );
}

interface InfoCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}

function InfoCard({ icon, label, value, sub }: InfoCardProps) {
  return (
    <div className="min-w-[180px] rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2">
      <div className="flex items-center gap-2 text-xs text-slate-400">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1 font-mono text-sm">{value}</div>
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

interface OrdersTableProps {
  orders: MarketDataSnapshot["orders"];
}

function OrdersTable({ orders }: OrdersTableProps) {
  if (!orders.length) {
    return <div className="text-xs text-slate-400">No open orders.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="text-slate-400">
          <tr>
            <th className="px-2 py-1 text-left">Order</th>
            <th className="px-2 py-1 text-left">Side</th>
            <th className="px-2 py-1 text-right">Price</th>
            <th className="px-2 py-1 text-right">Filled</th>
            <th className="px-2 py-1 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.order_id}>
              <td className="px-2 py-1 font-mono">{order.order_id}</td>
              <td className="px-2 py-1">{order.side}</td>
              <td className="px-2 py-1 text-right font-mono">
                {order.price.toFixed(2)}
              </td>
              <td className="px-2 py-1 text-right font-mono">
                {order.filled_amount.toFixed(4)}
              </td>
              <td className="px-2 py-1 text-right">{order.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
