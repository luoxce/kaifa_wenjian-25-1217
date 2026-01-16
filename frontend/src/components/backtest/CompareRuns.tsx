import BilingualLabel from "@/components/ui/BilingualLabel";
import { Badge } from "@/components/ui/badge";
import type { BacktestRun } from "@/types/schema";

interface HistoryRunRow {
  backtest_id: number;
  name?: string;
  run_id?: string;
  symbol: string;
  timeframe: string;
  total_return?: number;
  max_drawdown?: number;
  win_rate?: number;
  final_equity?: number;
  created_at?: number;
}

interface CompareRunsProps {
  runs: BacktestRun[];
  historyRuns: HistoryRunRow[];
  selectedIds: number[];
  selectedId?: number;
  onToggle: (id: number) => void;
  onRemove: (id: number) => void;
  onSelect: (id: number) => void;
  onLoadHistory: (row: HistoryRunRow) => void;
}

export default function CompareRuns({
  runs,
  historyRuns,
  selectedIds,
  selectedId,
  onToggle,
  onRemove,
  onSelect,
  onLoadHistory,
}: CompareRunsProps) {
  if (!runs.length && !historyRuns.length) {
    return <div className="text-[11px] text-slate-500">暂无回测记录 / No runs.</div>;
  }

  return (
    <div className="rounded-xl border border-[#1c1c1c] bg-[#0a0a0a] p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <BilingualLabel zh="回测运行列表" en="Runs" compact />
        <span className="text-[10px] text-slate-500">最多对比 3 次 / Max 3</span>
      </div>
      <div className="space-y-2">
        {runs.map((run) => {
          const checked = selectedIds.includes(run.id);
          return (
            <div
              key={run.id}
              className="flex items-center justify-between rounded border border-[#1c1c1c] bg-[#050505] px-2 py-2"
            >
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={checked} onChange={() => onToggle(run.id)} />
                <button
                  className="text-left text-[11px] text-slate-300 hover:text-slate-100"
                  onClick={() => onSelect(run.id)}
                >
                  <div className="font-mono">{run.name ?? run.runId ?? `Run ${run.id}`}</div>
                  <div className="text-[10px] text-slate-500">
                    #{run.id} · {formatDate(run.createdAt)} · {run.symbol}
                  </div>
                </button>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={selectedId === run.id ? "info" : "default"}>{run.timeframe}</Badge>
                <button
                  className="text-[10px] text-rose-300 hover:text-rose-200"
                  onClick={() => onRemove(run.id)}
                >
                  移除 / Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 text-[10px] text-slate-500">最多选择 3 次回测进行权益曲线对比。</div>

      <div className="mt-4 border-t border-[#1c1c1c] pt-3">
        <BilingualLabel zh="历史回测" en="History (DB)" compact />
        <div className="mt-2 space-y-2">
          {historyRuns.length === 0 ? (
            <div className="text-[11px] text-slate-500">暂无历史 / No history.</div>
          ) : (
            historyRuns.map((row) => (
              <div
                key={row.backtest_id}
                className="flex items-center justify-between rounded border border-[#1c1c1c] bg-[#050505] px-2 py-2"
              >
                <div>
                  <div className="font-mono text-[11px] text-slate-300">
                    {row.name ?? row.run_id ?? `Run ${row.backtest_id}`}
                  </div>
                  <div className="text-[10px] text-slate-500">
                    #{row.backtest_id} · {row.timeframe} · {formatDate(row.created_at)} · {row.symbol}
                  </div>
                </div>
                <button
                  className="text-[10px] text-emerald-300 hover:text-emerald-200"
                  onClick={() => onLoadHistory(row)}
                >
                  加载 / Load
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function formatDate(ts?: number) {
  if (!ts) return "-";
  const date = new Date(ts * (ts < 1e12 ? 1000 : 1));
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
