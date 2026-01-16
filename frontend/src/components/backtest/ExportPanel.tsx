import BilingualLabel from "@/components/ui/BilingualLabel";
import { EXPORT_ITEMS } from "@/lib/i18n/backtestLabels";

import type { BacktestRun } from "@/types/schema";

export default function ExportPanel({
  run,
  onExport,
}: {
  run: BacktestRun;
  onExport: (run: BacktestRun, type: "equity" | "trades" | "positions") => void;
}) {
  return (
    <div className="grid gap-3">
      {EXPORT_ITEMS.map((item) => (
        <div key={item.key} className="rounded-lg border border-[#1c1c1c] bg-[#050505] p-3">
          <div className="flex items-center justify-between">
            <BilingualLabel zh={item.zh} en={item.en} />
            <button
              className="rounded border border-[#27272a] px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800/50"
              onClick={() => onExport(run, item.key as "equity" | "trades" | "positions")}
            >
              下载 / Download
            </button>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">
            {item.descZh} / {item.descEn}
          </div>
          <div className="mt-2 font-mono text-[11px] text-slate-400">{item.filename}</div>
        </div>
      ))}
    </div>
  );
}
