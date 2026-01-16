import { useMemo, useState } from "react";

import BilingualLabel from "@/components/ui/BilingualLabel";
import { Badge } from "@/components/ui/badge";
import { TRADE_COLUMNS } from "@/lib/i18n/backtestLabels";
import type { BacktestTrade } from "@/types/schema";
import { cn } from "@/lib/utils";

type SortKey = keyof BacktestTrade | "pnl" | "durationSec";

export default function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("exitTime");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const next = [...trades];
    next.sort((a, b) => {
      const left = toSortable(a, sortKey);
      const right = toSortable(b, sortKey);
      const delta = left > right ? 1 : left < right ? -1 : 0;
      return direction === "asc" ? delta : -delta;
    });
    return next;
  }, [trades, sortKey, direction]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) {
      setDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDirection("desc");
    }
  };

  if (!trades.length) {
    return <div className="text-xs text-slate-500">暂无交易 / No trades yet.</div>;
  }

  return (
    <div className="max-h-[360px] overflow-auto rounded-lg border border-[#1c1c1c] bg-[#050505]">
      <table className="w-full text-[11px] tabular-nums">
        <thead className="sticky top-0 bg-[#0a0a0a] text-slate-400">
          <tr>
            {TRADE_COLUMNS.map((col) => (
              <Header
                key={col.key}
                label={<BilingualLabel zh={col.zh} en={col.en} compact />}
                onClick={() => toggle(col.key as SortKey)}
                align={col.align as "left" | "right" | undefined}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((trade) => (
            <tr key={trade.id} className="border-b border-[#1c1c1c]">
              <td className="px-2 py-1 font-mono text-slate-300">{trade.entryTime}</td>
              <td className="px-2 py-1 font-mono text-slate-300">{trade.exitTime}</td>
              <td className="px-2 py-1">
                <Badge variant={trade.side === "long" ? "success" : "danger"}>
                  {trade.side === "long" ? "多 / Long" : "空 / Short"}
                </Badge>
              </td>
              <td className="px-2 py-1 text-right font-mono text-slate-200">
                {trade.entryPrice.toFixed(2)}
              </td>
              <td className="px-2 py-1 text-right font-mono text-slate-200">
                {trade.exitPrice.toFixed(2)}
              </td>
              <td className="px-2 py-1 text-right font-mono text-slate-200">
                {trade.qty.toFixed(4)}
              </td>
              <td
                className={cn(
                  "px-2 py-1 text-right font-mono",
                  trade.pnl >= 0 ? "text-emerald-300" : "text-rose-300"
                )}
              >
                {trade.pnl.toFixed(2)}
              </td>
              <td
                className={cn(
                  "px-2 py-1 text-right font-mono",
                  trade.pnlPct >= 0 ? "text-emerald-300" : "text-rose-300"
                )}
              >
                {trade.pnlPct.toFixed(2)}%
              </td>
              <td className="px-2 py-1 text-right font-mono text-slate-300">
                {Math.round(trade.durationSec / 60)}m
              </td>
              <td className="px-2 py-1 text-slate-400">{trade.reason ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Header({
  label,
  onClick,
  align,
}: {
  label: React.ReactNode;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <th
      className={cn(
        "px-2 py-2",
        align === "right" ? "text-right" : "text-left",
        "cursor-pointer select-none"
      )}
      onClick={onClick}
    >
      {label}
    </th>
  );
}

const toSortable = (trade: BacktestTrade, key: SortKey) => {
  switch (key) {
    case "entryTime":
    case "exitTime":
      return trade[key] ? new Date(trade[key]).getTime() : 0;
    case "side":
      return trade.side === "long" ? 1 : 0;
    case "reason":
      return trade.reason ? trade.reason.charCodeAt(0) : 0;
    default:
      return Number((trade as BacktestTrade)[key] ?? 0);
  }
};
