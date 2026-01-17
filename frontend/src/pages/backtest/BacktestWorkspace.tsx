import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import ChartPanel from "@/components/backtest/ChartPanel";
import CompareRuns from "@/components/backtest/CompareRuns";
import ConfigPanel, { type BacktestFormState } from "@/components/backtest/ConfigPanel";
import ResultsPanel from "@/components/backtest/ResultsPanel";
import TopBar, { type RunStatus } from "@/components/backtest/TopBar";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useBacktestRuns } from "@/hooks/useBacktestRuns";
import { useSocket } from "@/hooks/useSocket";
import { buildDetails, buildSummary, parseEquityCurve, parseTrades } from "@/lib/backtestMetrics";
import type { BacktestRun, Candle, SystemHealth } from "@/types/schema";

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
const wsBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;

type StrategyOption = { key: string; name: string };

type BacktestRow = {
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
  metrics_json?: string;
};

const defaultForm: BacktestFormState = {
  symbol: "BTC/USDT:USDT",
  timeframe: "1h",
  startTime: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
  endTime: new Date().toISOString(),
  initialCapital: 10000,
  leverage: 1,
  feeRate: 0.0005,
  slippageBps: 2,
  slippageModel: "fixed",
  orderSizeMode: "fixedNotional",
  orderSizeValue: 1000,
  allowShort: true,
  fundingEnabled: true,
  risk: {
    maxDrawdown: 0.3,
    maxPosition: 1,
  },
  strategyParams: {},
  strategy: "ema_trend",
  limit: 2000,
  signalWindow: 300,
  name: "",
};

const presets = [
  {
    label: "15m",
    values: { timeframe: "15m", limit: 3000, signalWindow: 500 } as Partial<BacktestFormState>,
  },
  {
    label: "1h",
    values: { timeframe: "1h", limit: 2000, signalWindow: 300 } as Partial<BacktestFormState>,
  },
  {
    label: "4h",
    values: { timeframe: "4h", limit: 1500, signalWindow: 200 } as Partial<BacktestFormState>,
  },
  {
    label: "1d",
    values: { timeframe: "1d", limit: 1000, signalWindow: 120 } as Partial<BacktestFormState>,
  },
];

const fetchJson = async (url: string, init?: RequestInit) => {
  const res = await fetch(url, init);
  const text = await res.text();
  let data: any = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = {};
    }
  }
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message || data.error)) ??
      `Request failed: ${res.status}`;
    throw new Error(detail);
  }
  return data;
};

export default function BacktestWorkspace() {
  const [form, setForm] = useState<BacktestFormState>(defaultForm);
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { runs, selectedRun, comparedRuns, addRun, removeRun, selectRun, toggleCompare } =
    useBacktestRuns();
  const { status: wsStatus } = useSocket(wsBase ? `${wsBase}/ws/market` : undefined);

  const { data: strategies = [] } = useQuery<StrategyOption[]>({
    queryKey: ["backtest-strategies"],
    queryFn: () => fetchJson(`${apiBase}/api/backtest/strategies`).then((res) => res.data || []),
    enabled: Boolean(apiBase),
  });

  const { data: historyRuns = [] } = useQuery<BacktestRow[]>({
    queryKey: ["backtest-history"],
    queryFn: () => fetchJson(`${apiBase}/api/backtests?limit=30`).then((res) => res.data || []),
    enabled: Boolean(apiBase),
  });

  const { data: apiHealth } = useQuery<SystemHealth>({
    queryKey: ["api-health"],
    queryFn: () => fetchJson(`${apiBase}/api/health`),
    enabled: Boolean(apiBase),
    refetchInterval: 15000,
  });

  const writeEnabled = apiHealth?.api_write_enabled ?? true;

  const { data: coverageRows = [] } = useQuery<
    Array<{
      timeframe: string;
      start_ts: number | null;
      end_ts: number | null;
    }>
  >({
    queryKey: ["backtest-coverage", form.symbol],
    queryFn: () =>
      fetchJson(`${apiBase}/api/data-health/coverage?symbol=${encodeURIComponent(form.symbol)}`).then(
        (res) => res.timeframes || []
      ),
    enabled: Boolean(apiBase),
  });

  useEffect(() => {
    if (!strategies.length) return;
    if (!strategies.find((item) => item.key === form.strategy)) {
      setForm((prev) => ({ ...prev, strategy: strategies[0].key }));
    }
  }, [strategies, form.strategy]);

  const { data: candles = [], isLoading: candlesLoading } = useQuery<Candle[]>({
    queryKey: ["backtest-candles", form.symbol, form.timeframe, form.limit],
    queryFn: () =>
      fetchJson(
        `${apiBase}/api/market/candles?symbol=${encodeURIComponent(
          form.symbol
        )}&timeframe=${form.timeframe}&limit=${form.limit}`
      ).then((res) => res.data || []),
    enabled: Boolean(apiBase),
  });

  const timeframeOptions = coverageRows.length
    ? coverageRows.map((row) => row.timeframe)
    : ["15m", "1h", "4h", "1d"];
  const selectedCoverage = coverageRows.find((row) => row.timeframe === form.timeframe);
  const earliestTs = normalizeTs(selectedCoverage?.start_ts);
  const latestTs = normalizeTs(selectedCoverage?.end_ts);
  const earliestLabel = earliestTs ? formatDate(earliestTs) : "-";
  const latestLabel = latestTs ? formatDate(latestTs) : "-";

  const [limitNote, setLimitNote] = useState<string | null>(null);

  useEffect(() => {
    if (!timeframeOptions.length) return;
    if (!timeframeOptions.includes(form.timeframe)) {
      setForm((prev) => ({ ...prev, timeframe: timeframeOptions[0] }));
    }
  }, [timeframeOptions, form.timeframe]);

  useEffect(() => {
    const intervalMs = timeframeToMs(form.timeframe);
    if (!intervalMs) return;
    let startMs = Date.parse(form.startTime);
    let endMs = Date.parse(form.endTime);
    const fallbackEnd = latestTs ?? Date.now();
    if (!Number.isFinite(endMs)) {
      endMs = fallbackEnd;
    }
    if (!Number.isFinite(startMs)) {
      startMs = earliestTs ?? fallbackEnd - intervalMs * 300;
    }
    if (earliestTs && startMs < earliestTs) startMs = earliestTs;
    if (latestTs && endMs > latestTs) endMs = latestTs;
    if (startMs > endMs) startMs = endMs;

    let nextLimit = Math.floor((endMs - startMs) / intervalMs) + 1;
    let note: string | null = null;
    if (nextLimit < 1) nextLimit = 1;
    if (nextLimit > 5000) {
      nextLimit = 5000;
      const adjustedStart = endMs - (nextLimit - 1) * intervalMs;
      startMs = earliestTs ? Math.max(earliestTs, adjustedStart) : adjustedStart;
      note = "K 线数量超过 5000，已自动截断区间 / Limit capped at 5000.";
    }

    const nextStartIso = new Date(startMs).toISOString();
    const nextEndIso = new Date(endMs).toISOString();
    const nextSignal = Math.min(form.signalWindow, nextLimit);

    const changed =
      nextStartIso !== form.startTime ||
      nextEndIso !== form.endTime ||
      nextLimit !== form.limit ||
      nextSignal !== form.signalWindow;
    if (changed) {
      setForm((prev) => ({
        ...prev,
        startTime: nextStartIso,
        endTime: nextEndIso,
        limit: nextLimit,
        signalWindow: nextSignal,
      }));
    }
    setLimitNote(note);
  }, [
    form.timeframe,
    form.startTime,
    form.endTime,
    form.signalWindow,
    form.limit,
    earliestTs,
    latestTs,
  ]);

  const mutation = useMutation({
    mutationFn: async () => {
      const startTs = toMs(form.startTime);
      const endTs = toMs(form.endTime);
      const payload = {
        symbol: form.symbol,
        timeframe: form.timeframe,
        strategy: form.strategy,
        limit: form.limit,
        signal_window: form.signalWindow,
        initial_capital: form.initialCapital,
        fee_rate: form.feeRate,
        name: form.name || null,
        start_ts: startTs,
        end_ts: endTs,
        slippage_bps: form.slippageBps,
        slippage_model: form.slippageModel,
        order_size_mode: form.orderSizeMode,
        order_size_value: form.orderSizeValue,
        allow_short: form.allowShort,
        funding_enabled: form.fundingEnabled,
        leverage: form.leverage ?? 1,
        risk: {
          max_drawdown: form.risk.maxDrawdown,
          max_position: form.risk.maxPosition,
        },
        strategy_params: form.strategyParams,
      };
      const response = await fetchJson(`${apiBase}/api/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const backtestId = response.backtest_id;
      if (!backtestId) {
        throw new Error("Backtest ID missing");
      }
      const detail = await fetchJson(`${apiBase}/api/backtests/${backtestId}`);
      return { detail: detail.data, run: response };
    },
    onSuccess: ({ detail, run }) => {
      const newRun = mapRun(detail, form, candles, run?.metrics);
      addRun(newRun);
      setRunStatus("done");
      setErrorMessage(null);
    },
    onError: (error) => {
      setRunStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Backtest failed.");
    },
  });

  useEffect(() => {
    if (mutation.isPending) {
      setRunStatus("running");
    }
  }, [mutation.isPending]);

  const activeRun = selectedRun ?? runs[0];
  const rangeLabel = useMemo(
    () => buildRangeLabel(activeRun?.startTs, activeRun?.endTs, form.startTime, form.endTime),
    [activeRun?.startTs, activeRun?.endTs, form.startTime, form.endTime]
  );

  return (
    <div className="min-h-screen bg-[#050505] p-4 text-slate-200">
      <TopBar
        symbol={form.symbol}
        timeframe={form.timeframe}
        rangeLabel={rangeLabel}
        status={runStatus}
        wsStatus={wsStatus === "open" ? "open" : wsStatus === "connecting" ? "connecting" : "closed"}
        onRun={() => mutation.mutate()}
        disabled={!apiBase || mutation.isPending || !writeEnabled}
      />

      <ResizablePanelGroup
        direction="horizontal"
        className="mt-4 h-[calc(100vh-120px)] rounded-xl border border-[#1c1c1c] bg-[#050505]"
      >
        <ResizablePanel defaultSize={26} minSize={20}>
          <div className="h-full overflow-hidden p-3">
            <ConfigPanel
              value={form}
              onChange={setForm}
              onRun={() => mutation.mutate()}
              strategies={strategies}
              presets={presets}
              timeframeOptions={timeframeOptions}
              earliestLabel={earliestLabel}
              latestLabel={latestLabel}
              limitNote={limitNote}
              running={mutation.isPending}
              apiEnabled={Boolean(apiBase)}
              writeEnabled={writeEnabled}
              errorMessage={errorMessage}
              onReset={() => setForm(defaultForm)}
            />
          </div>
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={48} minSize={35}>
          <div className="h-full overflow-hidden p-3">
            <ChartPanel
              candles={candles}
              selectedRun={activeRun}
              compareRuns={comparedRuns}
              loading={candlesLoading}
            />
          </div>
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={26} minSize={22}>
          <div className="h-full overflow-hidden p-3">
            <ResultsPanel run={activeRun} onExport={handleExport} />
            <div className="mt-3">
              <CompareRuns
                runs={runs}
                historyRuns={historyRuns}
                selectedIds={comparedRuns.map((run) => run.id)}
                onToggle={toggleCompare}
                onRemove={removeRun}
                onLoadHistory={handleLoadHistory}
                onSelect={selectRun}
                selectedId={activeRun?.id}
              />
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );

  function handleExport(run: BacktestRun, type: "equity" | "trades" | "positions") {
    if (type === "equity") {
      downloadCsv(
        `equity_curve_${run.id}.csv`,
        ["t", "equity", "drawdown"],
        run.equityCurve.map((row) => [row.t, row.equity, row.drawdown])
      );
    } else if (type === "trades") {
      downloadCsv(
        `trades_${run.id}.csv`,
        [
          "id",
          "entryTime",
          "exitTime",
          "side",
          "entryPrice",
          "exitPrice",
          "qty",
          "pnl",
          "pnlPct",
          "fee",
          "funding",
          "slippage",
          "durationSec",
          "reason",
        ],
        run.trades.map((trade) => [
          trade.id,
          trade.entryTime,
          trade.exitTime,
          trade.side,
          trade.entryPrice,
          trade.exitPrice,
          trade.qty,
          trade.pnl,
          trade.pnlPct,
          trade.fee,
          trade.funding,
          trade.slippage,
          trade.durationSec,
          trade.reason ?? "",
        ])
      );
    } else {
      downloadCsv(
        `positions_${run.id}.csv`,
        ["t", "position", "notional", "leverage"],
        (run.positions ?? []).map((row) => [row.t, row.position, row.notional, row.leverage])
      );
    }
  }

  async function handleLoadHistory(row: BacktestRow) {
    if (!apiBase) return;
    const detail = await fetchJson(`${apiBase}/api/backtests/${row.backtest_id}`);
    const payload = detail.data as Record<string, unknown>;
    const paramsPayload = safeJson<Record<string, any>>(
      payload.params_json ?? payload.strategy_params ?? {},
      {}
    );
    const execution = (paramsPayload.execution ?? {}) as Record<string, unknown>;
    const riskPayload = (paramsPayload.risk ?? {}) as Record<string, unknown>;
    const rangePayload = (paramsPayload.range ?? {}) as Record<string, unknown>;
    const strategyFromParams =
      typeof paramsPayload.strategy_key === "string" && paramsPayload.strategy_key
        ? paramsPayload.strategy_key
        : undefined;
    const strategyParamsPayload = paramsPayload.strategy_params;
    const strategyParams =
      strategyParamsPayload &&
      typeof strategyParamsPayload === "object" &&
      !Array.isArray(strategyParamsPayload)
        ? (strategyParamsPayload as Record<string, unknown>)
        : form.strategyParams;
    const rangeStart = normalizeTs(
      rangePayload.requested_start_ts ??
        rangePayload.requestedStartTs ??
        rangePayload.start_ts ??
        payload.start_ts ??
        payload.start_time ??
        payload.startTime
    );
    const rangeEnd = normalizeTs(
      rangePayload.requested_end_ts ??
        rangePayload.requestedEndTs ??
        rangePayload.end_ts ??
        payload.end_ts ??
        payload.end_time ??
        payload.endTime
    );
    const nextForm: BacktestFormState = {
      ...form,
      symbol: readString(payload.symbol ?? row.symbol, form.symbol),
      timeframe: readString(payload.timeframe ?? row.timeframe, form.timeframe),
      strategy: readString(payload.strategy ?? strategyFromParams, form.strategy),
      name: readText(payload.name ?? row.name, form.name ?? ""),
      initialCapital:
        readNumber(payload.initial_capital, form.initialCapital),
      feeRate: readNumber(execution.fee_rate, form.feeRate),
      slippageBps: readNumber(execution.slippage_bps, form.slippageBps),
      slippageModel: readString(execution.slippage_model, form.slippageModel),
      orderSizeMode: readString(execution.order_size_mode, form.orderSizeMode),
      orderSizeValue:
        readNumber(execution.order_size_value, form.orderSizeValue),
      allowShort: readBool(execution.allow_short, form.allowShort),
      fundingEnabled: readBool(execution.funding_enabled, form.fundingEnabled),
      leverage: readNumber(execution.leverage, form.leverage ?? 1),
      risk: {
        maxDrawdown:
          readNumber(
            riskPayload.max_drawdown ?? riskPayload.maxDrawdown,
            form.risk.maxDrawdown ?? 0
          ),
        maxPosition:
          readNumber(
            riskPayload.max_position ?? riskPayload.maxPosition,
            form.risk.maxPosition ?? 0
          ),
      },
      startTime: rangeStart ? new Date(rangeStart).toISOString() : form.startTime,
      endTime: rangeEnd ? new Date(rangeEnd).toISOString() : form.endTime,
      signalWindow: readNumber(
        paramsPayload.signal_window ?? payload.signal_window,
        form.signalWindow
      ),
      strategyParams,
    };
    setForm(nextForm);
    const candleResponse = await fetchJson(
      `${apiBase}/api/market/candles?symbol=${encodeURIComponent(
        nextForm.symbol
      )}&timeframe=${nextForm.timeframe}&limit=${nextForm.limit}`
    );
    const candleData = (candleResponse?.data ?? []) as Candle[];
    const run = mapRun(payload, nextForm, candleData, payload.metrics_json);
    addRun(run);
    selectRun(run.id);
    setRunStatus("done");
  }
}

function mapRun(
  detail: Record<string, unknown>,
  form: BacktestFormState,
  candles: Candle[],
  metrics?: Record<string, unknown>
): BacktestRun {
  const equityCurve = parseEquityCurve(detail.equity_curve_json ?? detail.equity_curve);
  const trades = parseTrades(detail.trade_log);
  const initialCapital = Number(detail.initial_capital ?? form.initialCapital ?? 10000);
  const summary = buildSummary({
    equityCurve,
    trades,
    initialCapital,
    timeframe: String(detail.timeframe ?? form.timeframe),
    metrics: safeJson(detail.metrics_json, metrics ?? {}),
  });
  const benchmarkReturn = computeBenchmarkReturn(candles);
  const details = buildDetails({
    equityCurve,
    trades,
    timeframe: String(detail.timeframe ?? form.timeframe),
    benchmarkReturn,
    strategyReturn: summary.totalReturn,
    initialCapital,
  });

  const startTs = normalizeTs(detail.start_ts ?? detail.startTs) ?? toMs(form.startTime);
  const endTs = normalizeTs(detail.end_ts ?? detail.endTs) ?? toMs(form.endTime);

  return {
    id: Number(detail.backtest_id ?? detail.id),
    runId: detail.run_id ? String(detail.run_id) : undefined,
    name: detail.name ? String(detail.name) : form.name,
    symbol: String(detail.symbol ?? form.symbol),
    timeframe: String(detail.timeframe ?? form.timeframe),
    createdAt: Number(detail.created_at ?? Date.now()),
    startTs,
    endTs,
    params: detail.params_json ? safeJson(detail.params_json, {}) : form.strategyParams,
    summary,
    details,
    equityCurve,
    trades,
    logs: [],
  };
}

function computeBenchmarkReturn(candles: Candle[]) {
  if (!candles.length) return null;
  const first = candles[0]?.open ?? candles[0]?.close;
  const last = candles[candles.length - 1]?.close;
  if (!first || !last) return null;
  return ((last - first) / first) * 100;
}

function safeJson<T>(value: unknown, fallback: T): T {
  if (!value) return fallback;
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as T;
    } catch {
      return fallback;
    }
  }
  return value as T;
}

function readNumber(value: unknown, fallback: number): number {
  if (value === undefined || value === null) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readString(value: unknown, fallback: string): string {
  if (typeof value === "string" && value) return value;
  return fallback;
}

function readText(value: unknown, fallback: string): string {
  if (value === undefined || value === null) return fallback;
  return String(value);
}

function readBool(value: unknown, fallback: boolean): boolean {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.toLowerCase() === "true";
  if (typeof value === "number") return value !== 0;
  return fallback;
}

function downloadCsv(filename: string, headers: string[], rows: Array<Array<unknown>>) {
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(row.map((cell) => `"${String(cell)}"`).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function normalizeTs(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  if (typeof value === "string") {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return numeric < 1e12 ? numeric * 1000 : numeric;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  const num = Number(value);
  if (!Number.isFinite(num)) return undefined;
  return num < 1e12 ? num * 1000 : num;
}

function toMs(value: string): number {
  const ts = Date.parse(value);
  return Number.isFinite(ts) ? ts : Date.now();
}

function buildRangeLabel(
  startTs?: number,
  endTs?: number,
  fallbackStart?: string,
  fallbackEnd?: string
) {
  const start = startTs ?? (fallbackStart ? toMs(fallbackStart) : undefined);
  const end = endTs ?? (fallbackEnd ? toMs(fallbackEnd) : undefined);
  if (!start || !end) {
    return "范围 / Range: -";
  }
  return `范围 / Range: ${formatDate(start)} ~ ${formatDate(end)}`;
}

function formatDate(ts: number) {
  const date = new Date(ts);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function timeframeToMs(timeframe: string) {
  if (timeframe.endsWith("m")) {
    return Number(timeframe.replace("m", "")) * 60 * 1000;
  }
  if (timeframe.endsWith("h")) {
    return Number(timeframe.replace("h", "")) * 60 * 60 * 1000;
  }
  if (timeframe.endsWith("d")) {
    return Number(timeframe.replace("d", "")) * 24 * 60 * 60 * 1000;
  }
  return 15 * 60 * 1000;
}
