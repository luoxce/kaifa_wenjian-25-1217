import { Badge } from "@/components/ui/badge";
import BilingualLabel from "@/components/ui/BilingualLabel";
import { cn } from "@/lib/utils";

export type RunStatus = "idle" | "running" | "done" | "error";

interface TopBarProps {
  symbol: string;
  timeframe: string;
  rangeLabel: string;
  status: RunStatus;
  wsStatus: "open" | "closed" | "connecting";
  onRun: () => void;
  disabled?: boolean;
}

export default function TopBar({
  symbol,
  timeframe,
  rangeLabel,
  status,
  wsStatus,
  onRun,
  disabled,
}: TopBarProps) {
  return (
    <div className="sticky top-0 z-20 flex items-center justify-between rounded-xl border border-[#1c1c1c] bg-[#0a0a0a]/90 px-4 py-3 backdrop-blur">
      <div className="space-y-1">
        <div className="text-sm font-semibold tracking-wide">回测工作台 / Backtest Workspace</div>
        <div className="text-[11px] text-slate-500">
          TradingView / QuantConnect style backtest console
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Badge className="font-mono">{symbol}</Badge>
          <Badge variant="info">{timeframe}</Badge>
          <Badge className="font-mono text-[10px] text-slate-400">{rangeLabel}</Badge>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status={status} />
          <WsPill status={wsStatus} />
        </div>
        <button
          className={cn(
            "rounded-md border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20",
            disabled && "cursor-not-allowed opacity-50"
          )}
          onClick={onRun}
          disabled={disabled}
        >
          <BilingualLabel zh="运行回测" en="Run Backtest" compact className="items-center" />
        </button>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: RunStatus }) {
  const styles = {
    idle: "text-slate-300 border-slate-700 bg-slate-800/40",
    running: "text-blue-300 border-blue-500/40 bg-blue-500/10",
    done: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
    error: "text-rose-300 border-rose-500/40 bg-rose-500/10",
  }[status];
  const label = {
    idle: "空闲 / Idle",
    running: "运行中 / Running",
    done: "完成 / Done",
    error: "错误 / Error",
  }[status];

  return (
    <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px]", styles)}>
      <span className="h-2 w-2 rounded-full bg-current" />
      {label}
    </span>
  );
}

function WsPill({ status }: { status: "open" | "closed" | "connecting" }) {
  const styles = {
    open: "text-emerald-300 border-emerald-500/40 bg-emerald-500/10",
    connecting: "text-amber-300 border-amber-500/40 bg-amber-500/10",
    closed: "text-slate-400 border-slate-700 bg-slate-800/40",
  }[status];
  const label = {
    open: "在线 / Open",
    connecting: "连接中 / Connecting",
    closed: "离线 / Closed",
  }[status];
  return (
    <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px]", styles)}>
      <span className="h-2 w-2 rounded-full bg-current" />
      WS {label}
    </span>
  );
}
