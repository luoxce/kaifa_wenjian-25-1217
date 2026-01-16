import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  CandleIntegrityEvent,
  CandleRepairJob,
  DataCoverageRow,
} from "@/types/schema";

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

const fetchCoverage = async (symbol: string): Promise<DataCoverageRow[]> => {
  if (!apiBase) return [];
  const res = await fetch(`${apiBase}/api/data-health/coverage?symbol=${symbol}`);
  const json = await res.json();
  return json.timeframes || [];
};

const fetchEvents = async (
  symbol: string,
  timeframe?: string
): Promise<CandleIntegrityEvent[]> => {
  if (!apiBase) return [];
  const tfParam = timeframe ? `&timeframe=${timeframe}` : "";
  const res = await fetch(
    `${apiBase}/api/data-health/integrity-events?symbol=${symbol}${tfParam}&limit=200`
  );
  const json = await res.json();
  return json.data || [];
};

const fetchRepairJobs = async (
  symbol?: string,
  timeframe?: string
): Promise<CandleRepairJob[]> => {
  if (!apiBase) return [];
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (timeframe) params.set("timeframe", timeframe);
  params.set("limit", "100");
  const res = await fetch(`${apiBase}/api/data-health/repair-jobs?${params}`);
  const json = await res.json();
  return json.data || [];
};

const postScan = async (payload: {
  symbol: string;
  timeframes: string[];
  range_start_ts?: number;
  range_end_ts?: number;
}) => {
  if (!apiBase) return null;
  const res = await fetch(`${apiBase}/api/data-health/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
};

const postRepair = async (payload: {
  symbol: string;
  timeframe: string;
  range_start_ts: number;
  range_end_ts: number;
  mode: "refetch" | "fill";
}) => {
  if (!apiBase) return null;
  const res = await fetch(`${apiBase}/api/data-health/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
};

export const useDataHealth = (symbol: string, timeframe?: string) => {
  const queryClient = useQueryClient();
  const coverageQuery = useQuery({
    queryKey: ["data-health-coverage", symbol],
    queryFn: () => fetchCoverage(symbol),
    enabled: Boolean(apiBase),
  });
  const eventsQuery = useQuery({
    queryKey: ["data-health-events", symbol, timeframe],
    queryFn: () => fetchEvents(symbol, timeframe),
    enabled: Boolean(apiBase),
  });
  const jobsQuery = useQuery({
    queryKey: ["data-health-jobs", symbol, timeframe],
    queryFn: () => fetchRepairJobs(symbol, timeframe),
    enabled: Boolean(apiBase),
  });

  const scanMutation = useMutation({
    mutationFn: postScan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-health-events", symbol] });
      queryClient.invalidateQueries({ queryKey: ["data-health-coverage", symbol] });
    },
  });

  const repairMutation = useMutation({
    mutationFn: postRepair,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-health-events", symbol] });
      queryClient.invalidateQueries({ queryKey: ["data-health-jobs", symbol] });
    },
  });

  return {
    coverageQuery,
    eventsQuery,
    jobsQuery,
    scanMutation,
    repairMutation,
  };
};

