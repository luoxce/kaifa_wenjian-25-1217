import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";

const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;

interface RLStatus {
  enabled: boolean;
  model_loaded: boolean;
  mode: string;
}

interface RLStats {
  total_decisions: number;
  rl_interventions: number;
  intervention_rate: number;
  win_rate: number;
  sharpe_ratio: number;
  avg_position?: number;
}

const fetchJson = async (path: string) => {
  if (!apiBase) throw new Error("API base URL missing.");
  const res = await fetch(`${apiBase}${path}`);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
};

export default function RLPerformance() {
  const [rlStatus, setRlStatus] = useState<RLStatus | null>(null);
  const [rlStats, setRlStats] = useState<RLStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (!apiBase) {
        setError("Set VITE_API_BASE_URL to enable RL monitoring.");
        setLoading(false);
        return;
      }
      try {
        const [status, stats] = await Promise.all([
          fetchJson("/api/rl/status"),
          fetchJson("/api/rl/stats"),
        ]);
        if (!active) return;
        setRlStatus(status);
        setRlStats(stats);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "RL status load failed.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    const id = window.setInterval(load, 30000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, []);

  const enabled = rlStatus?.enabled ?? false;
  const badgeVariant = enabled ? "success" : "default";
  const winRatePct = Math.round((rlStats?.win_rate ?? 0) * 100);
  const interventionRatePct = Math.round((rlStats?.intervention_rate ?? 0) * 100);

  return (
    <Card className="w-full">
      <CardHeader className="flex items-center justify-between gap-2">
        <CardTitle>RL Performance</CardTitle>
        <Badge variant={badgeVariant}>{enabled ? "Active" : "Disabled"}</Badge>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </div>
        ) : error ? (
          <div className="text-xs text-rose-400">{error}</div>
        ) : (
          <div className="grid gap-4 text-xs text-slate-300 md:grid-cols-2">
            <div>
              <div className="text-[11px] text-slate-500">Mode</div>
              <div className="font-mono text-slate-200">{rlStatus?.mode ?? "-"}</div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500">Model Loaded</div>
              <div className="font-mono text-slate-200">
                {rlStatus?.model_loaded ? "YES" : "NO"}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500">Total Decisions</div>
              <div className="font-mono text-slate-200">
                {rlStats?.total_decisions ?? 0}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500">Interventions</div>
              <div className="font-mono text-slate-200">
                {rlStats?.rl_interventions ?? 0} ({interventionRatePct}%)
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500">Avg Position</div>
              <div className="font-mono text-slate-200">
                {rlStats?.avg_position?.toFixed?.(2) ?? "-"}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500">Sharpe Ratio</div>
              <div className="font-mono text-slate-200">
                {rlStats?.sharpe_ratio?.toFixed?.(2) ?? "-"}
              </div>
            </div>
            <div className="md:col-span-2">
              <div className="mb-2 text-[11px] text-slate-500">Win Rate</div>
              <Progress value={winRatePct} />
              <div className="mt-2 text-[11px] text-slate-400">{winRatePct}%</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
