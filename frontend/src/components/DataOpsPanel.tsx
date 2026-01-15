import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const postJson = async (path: string, payload?: Record<string, unknown>) => {
  if (!apiBase) return null;
  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : JSON.stringify({}),
  });
  return res.json();
};

export default function DataOpsPanel() {
  const [symbol, setSymbol] = useState("BTC/USDT:USDT");
  const [sinceDays, setSinceDays] = useState(30);
  const [timeframes, setTimeframes] = useState("15m,1h,4h,1d");
  const [lastResult, setLastResult] = useState("");

  const syncAccount = useMutation({
    mutationFn: () => postJson("/api/actions/sync_account", { symbol }),
    onSuccess: (data) => setLastResult(JSON.stringify(data)),
  });
  const syncOrders = useMutation({
    mutationFn: () => postJson("/api/actions/sync_orders"),
    onSuccess: (data) => setLastResult(JSON.stringify(data)),
  });
  const ingest = useMutation({
    mutationFn: () =>
      postJson("/api/actions/ingest", {
        symbol,
        since_days: Number(sinceDays),
        timeframes: timeframes.split(",").map((t) => t.trim()).filter(Boolean),
      }),
    onSuccess: (data) => setLastResult(JSON.stringify(data)),
  });

  return (
    <div className="space-y-3 text-xs">
      <div className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
        <div className="mb-2 text-[11px] text-slate-400">Database Update</div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <Field label="Symbol" value={symbol} onChange={setSymbol} />
          <Field
            label="Since Days"
            value={sinceDays}
            onChange={(v) => setSinceDays(Number(v))}
          />
          <Field
            label="Timeframes"
            value={timeframes}
            onChange={setTimeframes}
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            className="rounded bg-slate-800 px-3 py-1 text-[11px]"
            onClick={() => ingest.mutate()}
            disabled={!apiBase}
          >
            Ingest OHLCV
          </button>
          <button
            className="rounded bg-slate-800 px-3 py-1 text-[11px]"
            onClick={() => syncAccount.mutate()}
            disabled={!apiBase}
          >
            Sync Account
          </button>
          <button
            className="rounded bg-slate-800 px-3 py-1 text-[11px]"
            onClick={() => syncOrders.mutate()}
            disabled={!apiBase}
          >
            Sync Orders
          </button>
        </div>
        {!apiBase && (
          <div className="mt-2 text-[11px] text-rose-400">
            Set VITE_API_BASE_URL to enable API actions.
          </div>
        )}
      </div>

      <div className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
        <div className="mb-2 text-[11px] text-slate-400">Last Result</div>
        <pre className="max-h-40 overflow-auto text-[11px] text-slate-300">
          {lastResult || "No actions yet."}
        </pre>
      </div>
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
}

function Field({ label, value, onChange }: FieldProps) {
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
