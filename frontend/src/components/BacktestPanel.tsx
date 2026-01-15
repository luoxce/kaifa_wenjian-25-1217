import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type StrategyOption = {
  key: string;
  name: string;
};

type BacktestRow = {
  backtest_id: number;
  name: string;
  symbol: string;
  timeframe: string;
  total_return: number;
  max_drawdown: number;
  win_rate: number;
  final_equity: number;
  created_at: number;
};

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const fetchStrategies = async (): Promise<StrategyOption[]> => {
  if (!apiBase) return [];
  const res = await fetch(`${apiBase}/api/backtest/strategies`);
  const json = await res.json();
  return json.data || [];
};

const fetchBacktests = async (): Promise<BacktestRow[]> => {
  if (!apiBase) return [];
  const res = await fetch(`${apiBase}/api/backtests?limit=20`);
  const json = await res.json();
  return json.data || [];
};

const runBacktest = async (payload: Record<string, unknown>) => {
  if (!apiBase) return null;
  const res = await fetch(`${apiBase}/api/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
};

export default function BacktestPanel() {
  const queryClient = useQueryClient();
  const { data: strategies = [] } = useQuery({
    queryKey: ["backtest-strategies"],
    queryFn: fetchStrategies,
  });
  const { data: backtests = [] } = useQuery({
    queryKey: ["backtests"],
    queryFn: fetchBacktests,
    refetchInterval: 30000,
  });

  const defaultStrategy = useMemo(
    () => strategies[0]?.key || "ema_trend",
    [strategies]
  );

  const [form, setForm] = useState({
    symbol: "BTC/USDT:USDT",
    timeframe: "1h",
    strategy: defaultStrategy,
    limit: 2000,
    signal_window: 300,
    initial_capital: 10000,
    fee_rate: 0.0005,
    name: "",
  });

  const mutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtests"] });
    },
  });

  const onChange = (key: string, value: string | number) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-3 text-xs">
      <div className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
        <div className="mb-2 text-[11px] text-slate-400">Run Backtest</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Input label="Symbol" value={form.symbol} onChange={(v) => onChange("symbol", v)} />
          <Input
            label="Timeframe"
            value={form.timeframe}
            onChange={(v) => onChange("timeframe", v)}
          />
          <Select
            label="Strategy"
            value={form.strategy}
            options={strategies.length ? strategies : [{ key: "ema_trend", name: "ema_trend" }]}
            onChange={(v) => onChange("strategy", v)}
          />
          <Input
            label="Limit"
            value={form.limit}
            onChange={(v) => onChange("limit", Number(v))}
          />
          <Input
            label="Signal Window"
            value={form.signal_window}
            onChange={(v) => onChange("signal_window", Number(v))}
          />
          <Input
            label="Initial Capital"
            value={form.initial_capital}
            onChange={(v) => onChange("initial_capital", Number(v))}
          />
          <Input
            label="Fee Rate"
            value={form.fee_rate}
            onChange={(v) => onChange("fee_rate", Number(v))}
          />
          <Input label="Name" value={form.name} onChange={(v) => onChange("name", v)} />
        </div>
        <button
          className="mt-2 rounded bg-emerald-500/20 px-3 py-1 text-[11px] text-emerald-300"
          onClick={() => mutation.mutate(form)}
          disabled={!apiBase}
        >
          Run Backtest
        </button>
        {!apiBase && (
          <div className="mt-2 text-[11px] text-rose-400">
            Set VITE_API_BASE_URL to enable backtest API.
          </div>
        )}
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
                  <th className="px-2 py-1 text-left">Strategy</th>
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
                    <td className="px-2 py-1">{row.name}</td>
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

interface InputProps {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
}

function Input({ label, value, onChange }: InputProps) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-400">
      {label}
      <input
        className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-[11px] text-slate-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

interface SelectProps {
  label: string;
  value: string;
  options: StrategyOption[];
  onChange: (value: string) => void;
}

function Select({ label, value, options, onChange }: SelectProps) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-400">
      {label}
      <select
        className="rounded border border-slate-800 bg-slate-950 px-2 py-1 text-[11px] text-slate-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}
