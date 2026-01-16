import type { ReactNode } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { BacktestRun } from "@/types/schema";
import SummaryCards from "@/components/backtest/SummaryCards";
import TradesTable from "@/components/backtest/TradesTable";
import ExportPanel from "@/components/backtest/ExportPanel";
import BilingualLabel from "@/components/ui/BilingualLabel";
import { BACKTEST_TABS, DETAIL_GROUPS } from "@/lib/i18n/backtestLabels";

interface ResultsPanelProps {
  run?: BacktestRun;
  onExport: (run: BacktestRun, type: "equity" | "trades" | "positions") => void;
}

export default function ResultsPanel({ run, onExport }: ResultsPanelProps) {
  return (
    <section className="flex h-full flex-col rounded-xl border border-[#1c1c1c] bg-[#0a0a0a]">
      <Tabs defaultValue="summary" className="flex h-full flex-col">
        <div className="border-b border-[#1c1c1c] px-4 py-3 text-xs text-slate-400">
          <TabsList className="gap-2">
            <TabsTrigger value="summary">
              <BilingualLabel zh={BACKTEST_TABS.summary.zh} en={BACKTEST_TABS.summary.en} compact />
            </TabsTrigger>
            <TabsTrigger value="details">
              <BilingualLabel zh={BACKTEST_TABS.details.zh} en={BACKTEST_TABS.details.en} compact />
            </TabsTrigger>
            <TabsTrigger value="trades">
              <BilingualLabel zh={BACKTEST_TABS.trades.zh} en={BACKTEST_TABS.trades.en} compact />
            </TabsTrigger>
            <TabsTrigger value="logs">
              <BilingualLabel zh={BACKTEST_TABS.logs.zh} en={BACKTEST_TABS.logs.en} compact />
            </TabsTrigger>
            <TabsTrigger value="export">
              <BilingualLabel zh={BACKTEST_TABS.export.zh} en={BACKTEST_TABS.export.en} compact />
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="summary" className="flex-1 overflow-auto p-4">
          {run ? <SummaryCards summary={run.summary} /> : <Empty />}
        </TabsContent>
        <TabsContent value="details" className="flex-1 overflow-auto p-4">
          {run ? <DetailsBlock run={run} /> : <Empty />}
        </TabsContent>
        <TabsContent value="trades" className="flex-1 overflow-auto p-4">
          {run ? <TradesTable trades={run.trades} /> : <Empty />}
        </TabsContent>
        <TabsContent value="logs" className="flex-1 overflow-auto p-4">
          {run ? <LogsBlock logs={run.logs} /> : <Empty />}
        </TabsContent>
        <TabsContent value="export" className="flex-1 overflow-auto p-4">
          {run ? <ExportPanel run={run} onExport={onExport} /> : <Empty />}
        </TabsContent>
      </Tabs>
    </section>
  );
}

function Empty() {
  return <div className="text-xs text-slate-500">请选择回测 / Select a run.</div>;
}

function LogsBlock({ logs }: { logs?: string[] }) {
  if (!logs?.length) {
    return <div className="text-xs text-slate-500">暂无日志 / No logs.</div>;
  }
  return (
    <div className="space-y-2">
      <button
        className="rounded border border-[#27272a] px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800/50"
        onClick={() => navigator.clipboard.writeText(logs.join("\n"))}
      >
        复制 / Copy
      </button>
      {logs.map((entry, idx) => (
        <div key={`${entry}-${idx}`} className="rounded border border-[#27272a] bg-[#050505] p-2">
          <div className="text-[11px] text-slate-300">{entry}</div>
        </div>
      ))}
    </div>
  );
}

function DetailsBlock({ run }: { run: BacktestRun }) {
  const { details } = run;
  return (
    <div className="grid gap-3">
      {DETAIL_GROUPS.map((group) => (
        <DetailsGroup key={group.key} title={{ zh: group.zh, en: group.en }}>
          {group.items.map((item) => {
            const block = details[group.key as keyof typeof details] as Record<string, number | null>;
            return (
              <DetailItem
                key={item.key}
                label={{ zh: item.zh, en: item.en }}
                value={block?.[item.key]}
                suffix={item.suffix}
              />
            );
          })}
        </DetailsGroup>
      ))}
    </div>
  );
}

function DetailsGroup({
  title,
  children,
}: {
  title: { zh: string; en: string };
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#1c1c1c] bg-[#050505] p-3">
      <BilingualLabel zh={title.zh} en={title.en} compact />
      <div className="mt-3 grid grid-cols-2 gap-2">{children}</div>
    </div>
  );
}

function DetailItem({
  label,
  value,
  suffix,
}: {
  label: { zh: string; en: string };
  value: number | null | undefined;
  suffix?: string;
}) {
  return (
    <div className="flex items-center justify-between text-[11px] text-slate-300">
      <BilingualLabel zh={label.zh} en={label.en} compact className="text-slate-400" />
      <span className="font-mono">
        {value === null || value === undefined || Number.isNaN(value)
          ? "-"
          : `${value.toFixed(2)}${suffix ?? ""}`}
      </span>
    </div>
  );
}
