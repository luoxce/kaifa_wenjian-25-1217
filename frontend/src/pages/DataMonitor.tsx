import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useDataHealth } from "@/hooks/useDataHealth";
import type { CandleIntegrityEvent } from "@/types/schema";
import { TIMEFRAMES } from "@/lib/constants";

const formatTs = (ts?: number | null) =>
  ts ? new Date(ts).toISOString().slice(0, 19).replace("T", " ") : "-";

const toDays = (ms: number) => Math.max(ms / 86_400_000, 0);

export default function DataMonitor() {
  const [symbol, setSymbol] = useState("BTC/USDT:USDT");
  const [timeframes, setTimeframes] = useState<string[]>([...TIMEFRAMES]);
  const [selectedEvent, setSelectedEvent] = useState<CandleIntegrityEvent | null>(
    null
  );
  const [mode, setMode] = useState<"refetch" | "fill">("refetch");

  const timeframeFilter = timeframes.length === 1 ? timeframes[0] : "";
  const { coverageQuery, eventsQuery, jobsQuery, scanMutation, repairMutation } =
    useDataHealth(symbol, timeframeFilter);

  const coverage = coverageQuery.data || [];
  const events = eventsQuery.data || [];
  const jobs = jobsQuery.data || [];

  const timelineData = useMemo(() => {
    if (!coverage.length) return [];
    const minStart = Math.min(
      ...coverage
        .map((row) => row.start_ts ?? Date.now())
        .filter(Boolean)
    );
    return coverage.map((row) => {
      const start = row.start_ts ?? minStart;
      const end = row.end_ts ?? start;
      const offset = toDays(start - minStart);
      const duration = toDays(end - start);
      return {
        timeframe: row.timeframe,
        offset,
        duration: Math.max(duration, 0.05),
        start,
        end,
      };
    });
  }, [coverage]);

  const handleScan = () => {
    scanMutation.mutate({ symbol, timeframes });
  };

  const handleRepair = () => {
    if (!selectedEvent?.start_ts || !selectedEvent?.end_ts) return;
    repairMutation.mutate({
      symbol,
      timeframe: selectedEvent.timeframe,
      range_start_ts: selectedEvent.start_ts,
      range_end_ts: selectedEvent.end_ts,
      mode,
    });
  };

  return (
    <div className="min-h-screen bg-[#050505] p-4 text-slate-100">
      <div className="mb-4 flex items-center justify-between">
        <div className="font-mono text-sm text-slate-200">DATA MONITOR</div>
        <a
          href="/"
          className="text-xs text-slate-400 transition hover:text-[#00ff9d]"
        >
          Back to Dashboard
        </a>
      </div>
      <div className="mb-4 rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex flex-col gap-1 text-[11px] text-slate-400">
            Symbol
            <input
              className="rounded border border-[#27272a] bg-[#050505] px-3 py-1 text-xs text-slate-100"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
            />
          </label>
          <div className="flex flex-col gap-1 text-[11px] text-slate-400">
            Timeframes
            <div className="flex flex-wrap gap-2">
              {TIMEFRAMES.map((tf) => (
                <label
                  key={tf}
                  className={`cursor-pointer rounded border px-2 py-1 ${
                    timeframes.includes(tf)
                      ? "border-[#00ff9d] text-[#00ff9d]"
                      : "border-[#27272a] text-slate-400"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mr-1"
                    checked={timeframes.includes(tf)}
                    onChange={() => {
                      setTimeframes((prev) =>
                        prev.includes(tf)
                          ? prev.filter((t) => t !== tf)
                          : [...prev, tf]
                      );
                    }}
                  />
                  {tf}
                </label>
              ))}
            </div>
          </div>
          <div className="ml-auto flex gap-2">
            <button
              className="rounded border border-[#3b82f6] px-3 py-2 text-xs text-[#3b82f6]"
              onClick={handleScan}
            >
              Scan Now
            </button>
            <button
              className="rounded border border-[#ff0055] px-3 py-2 text-xs text-[#ff0055]"
              disabled={!selectedEvent}
              onClick={handleRepair}
            >
              Repair Selected
            </button>
          </div>
        </div>
      </div>

      <section className="mb-4 rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
        <div className="mb-3 text-xs text-slate-400">K线条数概览</div>
        <div className="flex flex-wrap gap-2">
          {coverage.map((row) => (
            <div
              key={`count-${row.timeframe}`}
              className="rounded border border-[#1f1f1f] bg-[#050505] px-3 py-2 text-[11px]"
            >
              <div className="text-slate-500">{row.timeframe}</div>
              <div className="font-mono text-slate-200">{row.bars} 条</div>
            </div>
          ))}
          {coverage.length === 0 && (
            <div className="text-[11px] text-slate-500">暂无覆盖数据。</div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <section className="rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
          <div className="mb-3 text-xs text-slate-400">Coverage Overview</div>
          <div className="grid gap-3 md:grid-cols-2">
            {coverage.map((row) => (
              <div
                key={row.timeframe}
                className="rounded border border-[#1f1f1f] bg-[#050505] p-3 text-xs"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>{row.timeframe}</span>
                  <span>K线条数：{row.bars}</span>
                </div>
                <div className="mt-2 font-mono text-[11px]">
                  <div>Start: {formatTs(row.start_ts)}</div>
                  <div>End: {formatTs(row.end_ts)}</div>
                  <div>Missing est: {row.missing_bars_estimate}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
          <div className="mb-3 text-xs text-slate-400">Repair Jobs</div>
          <div className="space-y-2 text-[11px]">
            {jobs.length === 0 && (
              <div className="text-slate-500">No repair jobs.</div>
            )}
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="rounded border border-[#1f1f1f] bg-[#050505] p-2"
              >
                <div className="flex items-center justify-between text-slate-400">
                  <span className="font-mono">{job.job_id.slice(0, 8)}</span>
                  <span>{job.status}</span>
                </div>
                <div className="font-mono text-slate-500">
                  {job.timeframe} {formatTs(job.range_start_ts)} →{" "}
                  {formatTs(job.range_end_ts)}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="mt-4 rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
        <div className="mb-3 text-xs text-slate-400">Coverage Timeline</div>
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={timelineData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid stroke="#1f1f1f" horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={(value) => `${value.toFixed(1)}d`}
                stroke="#4b5563"
                fontSize={10}
              />
              <YAxis
                dataKey="timeframe"
                type="category"
                stroke="#4b5563"
                fontSize={10}
              />
              <Tooltip
                content={({ payload }) => {
                  if (!payload || !payload.length) return null;
                  const datum = payload[0].payload as {
                    start: number;
                    end: number;
                  };
                  return (
                    <div className="rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px] text-slate-200">
                      <div>Start: {formatTs(datum.start)}</div>
                      <div>End: {formatTs(datum.end)}</div>
                    </div>
                  );
                }}
              />
              <Bar dataKey="offset" stackId="range" fill="transparent" />
              <Bar dataKey="duration" stackId="range" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="mt-4 rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-4">
        <div className="mb-3 text-xs text-slate-400">Integrity Events</div>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="text-slate-500">
              <tr>
                <th className="px-2 py-1 text-left">Type</th>
                <th className="px-2 py-1 text-left">Timeframe</th>
                <th className="px-2 py-1 text-left">Range</th>
                <th className="px-2 py-1 text-right">Missing</th>
                <th className="px-2 py-1 text-right">Duplicate</th>
                <th className="px-2 py-1 text-left">Severity</th>
                <th className="px-2 py-1 text-left">Detected</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr
                  key={event.id}
                  className={`cursor-pointer border-b border-[#1f1f1f] last:border-0 ${
                    selectedEvent?.id === event.id ? "bg-[#111111]" : ""
                  }`}
                  onClick={() => setSelectedEvent(event)}
                >
                  <td className="px-2 py-1">{event.event_type}</td>
                  <td className="px-2 py-1">{event.timeframe}</td>
                  <td className="px-2 py-1 font-mono">
                    {formatTs(event.start_ts)} → {formatTs(event.end_ts)}
                  </td>
                  <td className="px-2 py-1 text-right font-mono">
                    {event.missing_bars ?? "-"}
                  </td>
                  <td className="px-2 py-1 text-right font-mono">
                    {event.duplicate_bars ?? "-"}
                  </td>
                  <td className="px-2 py-1">{event.severity}</td>
                  <td className="px-2 py-1 font-mono">
                    {formatTs(event.detected_at)}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td className="px-2 py-3 text-slate-500" colSpan={7}>
                    No integrity events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
          <span className="font-mono">
            Selected: {selectedEvent ? selectedEvent.event_type : "-"}
          </span>
          <label className="flex items-center gap-2">
            Mode
            <select
              className="rounded border border-[#27272a] bg-[#050505] px-2 py-1 text-[11px]"
              value={mode}
              onChange={(event) => setMode(event.target.value as "refetch" | "fill")}
            >
              <option value="refetch">refetch</option>
              <option value="fill">fill</option>
            </select>
          </label>
        </div>
      </section>
    </div>
  );
}
