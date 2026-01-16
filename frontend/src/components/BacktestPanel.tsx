import { useQuery } from "@tanstack/react-query";

type BacktestRow = {
  backtest_id: number;
  name?: string;
  symbol: string;
  timeframe: string;
  total_return?: number;
  max_drawdown?: number;
  win_rate?: number;
  final_equity?: number;
  created_at?: number;
};

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const fetchBacktests = async (): Promise<BacktestRow[]> => {
  if (!apiBase) return [];
  const res = await fetch(`${apiBase}/api/backtests?limit=10`);
  const json = await res.json();
  return json.data || [];
};

export default function BacktestPanel() {
  const { data: backtests = [] } = useQuery({
    queryKey: ["backtests"],
    queryFn: fetchBacktests,
    enabled: Boolean(apiBase),
  });

  return (
    <div className="space-y-3 text-xs">
      <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3">
        <div className="mb-2 text-[11px] text-slate-400">Backtest Workspace</div>
        <div className="text-[11px] text-slate-500">
          使用完整回测工作台进行参数配置与结果对比 / Configure and compare runs.
        </div>
        <a
          href="/backtest"
          className="mt-2 inline-flex rounded border border-emerald-500/30 px-3 py-1 text-[11px] text-emerald-300 hover:bg-emerald-500/10"
        >
          Open Backtest Workspace →
        </a>
      </div>

      <div className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
        <div className="mb-2 text-[11px] text-slate-400">Recent Backtests</div>
        {backtests.length === 0 ? (
          <div className="text-[11px] text-slate-500">No backtest results yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead className="text-slate-400">
                <tr>
                  <th className="px-2 py-1 text-left">ID</th>
                  <th className="px-2 py-1 text-left">Name</th>
                  <th className="px-2 py-1 text-left">TF</th>
                  <th className="px-2 py-1 text-right">Return %</th>
                  <th className="px-2 py-1 text-right">MDD %</th>
                  <th className="px-2 py-1 text-right">Win %</th>
                  <th className="px-2 py-1 text-right">Final</th>
                </tr>
              </thead>
              <tbody>
                {backtests.map((row) => (
                  <tr key={row.backtest_id}>
                    <td className="px-2 py-1 font-mono">{row.backtest_id}</td>
                    <td className="px-2 py-1">{row.name ?? "-"}</td>
                    <td className="px-2 py-1">{row.timeframe}</td>
                    <td className="px-2 py-1 text-right font-mono">
                      {row.total_return?.toFixed?.(2) ?? "-"}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {row.max_drawdown?.toFixed?.(2) ?? "-"}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {row.win_rate?.toFixed?.(2) ?? "-"}
                    </td>
                    <td className="px-2 py-1 text-right font-mono">
                      {row.final_equity?.toFixed?.(2) ?? "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
