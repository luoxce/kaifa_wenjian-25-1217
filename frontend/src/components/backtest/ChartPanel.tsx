import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import BilingualLabel from "@/components/ui/BilingualLabel";
import { BACKTEST_TABS } from "@/lib/i18n/backtestLabels";
import PriceChart from "@/components/PriceChart";
import type { BacktestEquityPoint, BacktestRun, Candle } from "@/types/schema";

interface ChartPanelProps {
  candles: Candle[];
  selectedRun?: BacktestRun;
  compareRuns: BacktestRun[];
  loading?: boolean;
}

export default function ChartPanel({
  candles,
  selectedRun,
  compareRuns,
  loading,
}: ChartPanelProps) {
  const overlays = buildEmaOverlays(candles, [9, 21, 55]);
  const runs = compareRuns.length ? compareRuns : selectedRun ? [selectedRun] : [];
  const comparisonData = buildComparisonData(runs);
  const rangeLabel = buildRangeLabel(selectedRun);

  return (
    <section className="flex h-full flex-col rounded-xl border border-[#1c1c1c] bg-[#0a0a0a]">
      <Tabs defaultValue="price" className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-[#1c1c1c] px-4 py-3 text-xs text-slate-400">
          <TabsList className="gap-2">
            <TabsTrigger value="price">
              <BilingualLabel zh={BACKTEST_TABS.price.zh} en={BACKTEST_TABS.price.en} compact />
            </TabsTrigger>
            <TabsTrigger value="equity">
              <BilingualLabel zh={BACKTEST_TABS.equity.zh} en={BACKTEST_TABS.equity.en} compact />
            </TabsTrigger>
            <TabsTrigger value="drawdown">
              <BilingualLabel zh={BACKTEST_TABS.drawdown.zh} en={BACKTEST_TABS.drawdown.en} compact />
            </TabsTrigger>
          </TabsList>
          <div className="text-[11px] text-slate-500">
            {selectedRun
              ? `${selectedRun.symbol} · ${selectedRun.timeframe}`
              : "未选择回测 / No run selected"}
            <span className="ml-3 font-mono">{rangeLabel}</span>
          </div>
        </div>

        <TabsContent value="price" className="mt-0 flex-1">
          {loading ? (
            <LoadingState />
          ) : !candles.length ? (
            <EmptyState />
          ) : (
            <div className="h-full">
              <PriceChart candles={candles} orders={[]} overlays={overlays} />
            </div>
          )}
        </TabsContent>
        <TabsContent value="equity" className="mt-0 flex-1">
          <div className="h-full px-4 py-4">
            {loading ? (
              <LoadingState />
            ) : comparisonData.length ? (
              <EquityChart data={comparisonData} dataKeys={buildLineKeys(runs)} />
            ) : (
              <EmptyState />
            )}
          </div>
        </TabsContent>
        <TabsContent value="drawdown" className="mt-0 flex-1">
          <div className="h-full px-4 py-4">
            {loading ? (
              <LoadingState />
            ) : comparisonData.length ? (
              <DrawdownChart data={comparisonData} dataKeys={buildLineKeys(runs)} />
            ) : (
              <EmptyState />
            )}
          </div>
        </TabsContent>
      </Tabs>
    </section>
  );
}

const buildLineKeys = (runs: BacktestRun[]) =>
  runs.map((run) => ({
    key: `run_${run.id}`,
    label: `${run.name ?? run.runId ?? `#${run.id}`} · ${run.timeframe}`,
  }));

const buildComparisonData = (runs: BacktestRun[]) => {
  const map = new Map<string, Record<string, number | string>>();
  runs.forEach((run) => {
    const sampled = sampleCurve(run.equityCurve, 1200);
    sampled.forEach((point) => {
      const entry = map.get(point.t) ?? { t: point.t };
      entry[`run_${run.id}`] = point.equity;
      entry[`drawdown_${run.id}`] = point.drawdown * 100;
      map.set(point.t, entry);
    });
  });
  return Array.from(map.values()).sort((a, b) => (a.t > b.t ? 1 : -1));
};

function EquityChart({
  data,
  dataKeys,
}: {
  data: Array<Record<string, number | string>>;
  dataKeys: Array<{ key: string; label: string }>;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <XAxis dataKey="t" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={40} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} domain={["auto", "auto"]} />
        <RechartsTooltip content={ChartTooltip} />
        {dataKeys.map((line, idx) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            stroke={lineColor(idx)}
            dot={false}
            strokeWidth={2}
            name={line.label}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({
  data,
  dataKeys,
}: {
  data: Array<Record<string, number | string>>;
  dataKeys: Array<{ key: string; label: string }>;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <XAxis dataKey="t" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={40} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 10 }} domain={["auto", "auto"]} />
        <RechartsTooltip content={ChartTooltip} />
        {dataKeys.map((line, idx) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={`drawdown_${line.key.replace("run_", "")}`}
            stroke={lineColor(idx)}
            dot={false}
            strokeWidth={2}
            name={`${line.label} DD`}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: any[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-[#1c1c1c] bg-[#050505] px-3 py-2 text-[11px] text-slate-200">
      <div className="mb-1 text-slate-500">{label}</div>
      {payload.map((item) => (
        <div key={item.dataKey} className="flex items-center justify-between gap-3">
          <span className="text-slate-400">{item.name}</span>
          <span className="font-mono">{Number(item.value).toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

const lineColor = (idx: number) => {
  const palette = ["#00ff9d", "#3b82f6", "#ff0055"];
  return palette[idx % palette.length];
};

const buildEmaOverlays = (candles: Candle[], periods: number[]) =>
  periods.map((period, idx) => ({
    id: `ema_${period}`,
    name: `EMA ${period}`,
    color: idx === 0 ? "#3b82f6" : idx === 1 ? "#f59e0b" : "#a855f7",
    data: calcEmaSeries(candles, period),
  }));

const calcEmaSeries = (candles: Candle[], period: number) => {
  if (!candles.length) return [];
  const multiplier = 2 / (period + 1);
  let ema = candles[0].close;
  return candles.map((candle) => {
    ema = (candle.close - ema) * multiplier + ema;
    return { time: candle.time, value: ema };
  });
};

const sampleCurve = (curve: BacktestEquityPoint[], maxPoints: number) => {
  if (curve.length <= maxPoints) return curve;
  const step = Math.ceil(curve.length / maxPoints);
  return curve.filter((_, idx) => idx % step === 0);
};

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center text-xs text-slate-500">
        <div>暂无图表数据</div>
        <div className="text-[10px]">Run Backtest to generate charts.</div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-24 w-64 animate-pulse rounded-lg border border-[#1c1c1c] bg-[#050505]" />
    </div>
  );
}

function buildRangeLabel(run?: BacktestRun) {
  if (!run?.startTs || !run?.endTs) return "范围 / Range: -";
  return `范围 / Range: ${formatDate(run.startTs)} ~ ${formatDate(run.endTs)}`;
}

function formatDate(ts: number) {
  const date = new Date(ts);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
