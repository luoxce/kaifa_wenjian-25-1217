import type { ReactNode } from "react";
import { Power, ShieldCheck, Zap } from "lucide-react";

import type { SystemHealth } from "@/types/schema";

interface HeaderBarProps {
  health: SystemHealth;
  onHalt?: () => void;
}

const formatLatency = (latency: number) => {
  if (latency < 0) return "n/a";
  return `${latency}ms`;
};

export default function HeaderBar({ health, onHalt }: HeaderBarProps) {
  const latency = health.latency_ms ?? -1;
  const latencyState = latency < 120 ? "good" : latency < 220 ? "warn" : "bad";
  const synced = Date.now() - health.last_sync_time < 60_000;
  const modeValue =
    health.okx_is_demo === undefined ? "UNKNOWN" : health.okx_is_demo ? "DEMO" : "LIVE";
  const modeTone =
    health.okx_is_demo === undefined ? "warn" : health.okx_is_demo ? "warn" : "good";

  return (
    <header className="flex h-12 items-center justify-between rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 px-4">
      <div className="flex items-center gap-4 font-mono text-sm tracking-[0.2em] text-slate-200">
        <span className="text-xs text-slate-500">QUANT</span>
        <span className="text-slate-100">TERMINAL</span>
        <a
          href="/backtest"
          className="text-[10px] text-slate-500 transition hover:text-[#00ff9d]"
        >
          BACKTEST
        </a>
        <a
          href="/data-monitor"
          className="text-[10px] text-slate-500 transition hover:text-[#00ff9d]"
        >
          DATA MONITOR
        </a>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-300">
        <StatusPill
          label="API LATENCY"
          value={formatLatency(latency)}
          tone={latencyState}
          icon={<Zap className="h-3.5 w-3.5" />}
        />
        <StatusPill
          label="SYNC"
          value={synced ? "SYNCED" : "DESYNC"}
          tone={synced ? "good" : "bad"}
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
        />
        <StatusPill
          label="MODE"
          value={modeValue}
          tone={modeTone}
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
        />
        <StatusPill
          label="RISK GUARD"
          value={health.trading_enabled ? "ON" : "OFF"}
          tone={health.trading_enabled ? "good" : "warn"}
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
        />
        <StatusPill
          label="WRITE"
          value={health.api_write_enabled ? "ENABLED" : "DISABLED"}
          tone={health.api_write_enabled ? "good" : "warn"}
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
        />
        <button
          className="flex items-center gap-2 rounded-md border border-[#ff0055] px-3 py-1 text-[11px] font-semibold text-[#ff0055] transition hover:bg-[#ff0055]/10"
          onClick={onHalt}
          type="button"
        >
          <Power className="h-3.5 w-3.5" />
          HALT TRADING
        </button>
      </div>
    </header>
  );
}

type Tone = "good" | "warn" | "bad";

interface StatusPillProps {
  label: string;
  value: string;
  tone: Tone;
  icon?: ReactNode;
}

const toneMap: Record<Tone, string> = {
  good: "bg-[#00ff9d] shadow-[0_0_8px_rgba(0,255,157,0.45)]",
  warn: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.45)]",
  bad: "bg-[#ff0055] shadow-[0_0_8px_rgba(255,0,85,0.45)]",
};

function StatusPill({ label, value, tone, icon }: StatusPillProps) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[#27272a] bg-[#0a0a0a] px-2 py-1">
      <span className={`h-2 w-2 rounded-full ${toneMap[tone]}`} />
      <span className="text-[10px] text-slate-500">{label}</span>
      <span className="font-mono text-[11px] text-slate-200">{value}</span>
      {icon && <span className="text-slate-400">{icon}</span>}
    </div>
  );
}
