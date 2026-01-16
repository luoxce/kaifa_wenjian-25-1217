import BilingualLabel from "@/components/ui/BilingualLabel";
import { SUMMARY_METRICS } from "@/lib/i18n/backtestLabels";
import type { BacktestSummary } from "@/types/schema";
import { cn } from "@/lib/utils";

const formatPct = (value: number) => `${value.toFixed(2)}%`;
const formatNum = (value: number) => value.toFixed(2);

export default function SummaryCards({ summary }: { summary: BacktestSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
      {SUMMARY_METRICS.map((item) => {
        const value = formatValue(summary, item.key, item.format);
        const isNegative =
          typeof value === "number" ? value < 0 : String(value).includes("-");
        return (
          <div
            key={item.key}
            className={cn(
              "rounded-lg border border-[#1c1c1c] bg-[#050505] px-3 py-3",
              item.star && "border-emerald-500/30"
            )}
          >
            <div className="flex items-center justify-between">
              <BilingualLabel zh={item.zh} en={item.en} compact />
              {item.star && <span className="text-amber-400">*</span>}
            </div>
            <div
              className={cn(
                "mt-2 font-mono text-lg tabular-nums",
                isNegative ? "text-rose-300" : "text-emerald-300"
              )}
            >
              {formatDisplay(summary, item.key, item.format)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatValue(summary: BacktestSummary, key: string, format?: string) {
  const value = (summary as Record<string, number>)[key];
  if (format === "duration") {
    return value;
  }
  if (format === "funding") {
    return summary.fundingPnl;
  }
  return value;
}

function formatDisplay(summary: BacktestSummary, key: string, format?: string) {
  if (format === "duration") {
    return `${Math.round(summary.maxDrawdownDuration / 3600)}h`;
  }
  if (format === "funding") {
    return `${summary.fundingPnl.toFixed(2)} (${formatPct(summary.fundingPnlRatio)})`;
  }
  const value = (summary as Record<string, number>)[key];
  if (format === "pct") {
    return formatPct(value);
  }
  if (format === "int") {
    return String(Math.round(value));
  }
  return formatNum(value);
}
