import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import HeaderBar from "@/components/dashboard/HeaderBar";
import ChartStage from "@/components/dashboard/ChartStage";
import DecisionStream from "@/components/dashboard/DecisionStream";
import ExecutionDeck from "@/components/dashboard/ExecutionDeck";
import { useMarketData } from "@/hooks/useMarketData";

const defaultSymbol =
  (import.meta.env.VITE_DASHBOARD_SYMBOL as string | undefined) ??
  "BTC/USDT:USDT";
const defaultTimeframe =
  (import.meta.env.VITE_DASHBOARD_TIMEFRAME as string | undefined) ?? "15m";
const allowedTimeframes = ["15m", "1h", "1d"];
const defaultLimitRaw = import.meta.env.VITE_DASHBOARD_LIMIT as
  | string
  | undefined;
const defaultLimit = Number.isFinite(Number(defaultLimitRaw))
  ? Number(defaultLimitRaw)
  : 200;
const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const loadSetting = (key: string, fallback: string) => {
  if (typeof window === "undefined") return fallback;
  return window.localStorage.getItem(key) ?? fallback;
};

const loadNumberSetting = (key: string, fallback: number) => {
  if (typeof window === "undefined") return fallback;
  const stored = window.localStorage.getItem(key);
  const parsed = stored ? Number(stored) : NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
};

const storeSetting = (key: string, value: string | number) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, String(value));
};

const clampLimit = (value: number) => {
  if (!Number.isFinite(value)) return defaultLimit;
  const intValue = Math.trunc(value);
  return Math.min(Math.max(intValue, 50), 5000);
};

const fetchJson = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
};

export default function DashboardLayout() {
  const initialTimeframe = allowedTimeframes.includes(defaultTimeframe)
    ? defaultTimeframe
    : "15m";
  const [symbol, setSymbol] = useState(() =>
    loadSetting("dashboardSymbol", defaultSymbol)
  );
  const [timeframe, setTimeframe] = useState(() =>
    loadSetting("dashboardTimeframe", initialTimeframe)
  );
  const [limit, setLimit] = useState(() =>
    clampLimit(loadNumberSetting("dashboardLimit", defaultLimit))
  );

  useEffect(() => {
    storeSetting("dashboardSymbol", symbol);
  }, [symbol]);

  useEffect(() => {
    storeSetting("dashboardTimeframe", timeframe);
  }, [timeframe]);

  useEffect(() => {
    storeSetting("dashboardLimit", limit);
  }, [limit]);

  const { data: symbolOptions = [] } = useQuery<string[]>({
    queryKey: ["market-symbols"],
    queryFn: () => fetchJson(`${apiBase}/api/market/symbols`).then((res) => res.data || []),
    enabled: Boolean(apiBase),
  });

  const { data: timeframeOptions = [] } = useQuery<string[]>({
    queryKey: ["market-timeframes", symbol],
    queryFn: () =>
      fetchJson(
        `${apiBase}/api/market/timeframes?symbol=${encodeURIComponent(symbol)}`
      ).then((res) => res.data || []),
    enabled: Boolean(apiBase && symbol),
  });

  const availableSymbols = symbolOptions.length ? symbolOptions : [defaultSymbol];
  const availableTimeframes = timeframeOptions.length ? timeframeOptions : allowedTimeframes;
  const handleLimitChange = (value: number) => {
    setLimit(clampLimit(value));
  };

  useEffect(() => {
    if (!availableSymbols.includes(symbol)) {
      setSymbol(availableSymbols[0]);
    }
  }, [availableSymbols, symbol]);

  useEffect(() => {
    if (!availableTimeframes.includes(timeframe)) {
      setTimeframe(availableTimeframes[0]);
    }
  }, [availableTimeframes, timeframe]);
  const { data, isLoading } = useMarketData({
    symbol,
    timeframe,
    limit,
  });

  if (isLoading || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050505] text-slate-400">
        Loading dashboard...
      </div>
    );
  }

  const { health, account, candles, orders, positions, decisions, trades } = data;
  const lastPrice = candles[candles.length - 1]?.close ?? 0;
  return (
    <div className="min-h-screen bg-[#050505] text-slate-100">
      <div className="grid h-screen grid-cols-[minmax(0,7fr)_minmax(0,3fr)] grid-rows-[48px_minmax(0,1fr)_minmax(0,0.55fr)] gap-3 p-3">
        <div className="col-span-2">
          <HeaderBar health={health} />
        </div>
        <div className="col-start-1 row-start-2">
          <ChartStage
            symbol={symbol}
            timeframe={timeframe}
            candles={candles}
            orders={orders}
            onTimeframeChange={setTimeframe}
            timeframeOptions={availableTimeframes}
            symbolOptions={availableSymbols}
            onSymbolChange={setSymbol}
            limit={limit}
            onLimitChange={handleLimitChange}
          />
        </div>
        <div className="col-start-2 row-start-2 row-span-2">
          <DecisionStream decisions={decisions} />
        </div>
        <div className="col-start-1 row-start-3">
          <ExecutionDeck
            account={account}
            positions={positions}
            orders={orders}
            trades={trades}
            symbol={symbol}
            lastPrice={lastPrice}
          />
        </div>
      </div>
    </div>
  );
}
