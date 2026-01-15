import { useEffect, useMemo, useRef } from "react";

import type { StrategyDecision } from "@/types/schema";

interface DecisionStreamProps {
  decisions: StrategyDecision[];
}

const formatTime = (timestamp: number) =>
  new Date(timestamp).toLocaleTimeString(undefined, { hour12: false });

export default function DecisionStream({ decisions }: DecisionStreamProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const items = useMemo(() => decisions.slice().reverse(), [decisions]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [items.length]);

  return (
    <aside className="flex h-full flex-col rounded-lg border border-[#27272a] bg-[#0a0a0a]/90">
      <div className="flex items-center justify-between border-b border-[#27272a] px-3 py-2 text-xs text-slate-400">
        <span className="font-mono text-slate-200">STREAM</span>
        <span className="font-mono">{decisions.length} events</span>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto px-3 py-3 text-xs"
      >
        {items.length === 0 && (
          <div className="text-slate-500">No decision events yet.</div>
        )}
        {items.map((item, idx) => {
          const signal = item.signal.toUpperCase();
          const tone =
            signal === "BUY"
              ? "text-[#00ff9d]"
              : signal === "SELL"
                ? "text-[#ff0055]"
                : "text-slate-300";
          return (
            <div
              key={`${item.timestamp}-${idx}`}
              className="rounded-md border border-[#1f1f1f] bg-[#050505] px-3 py-2"
            >
              <div className="mb-1 flex items-center gap-2 text-[10px] text-slate-500">
                <span className="font-mono">[{formatTime(item.timestamp)}]</span>
                <span className="rounded bg-[#111827] px-1 py-0.5 text-[10px] text-[#3b82f6]">
                  STRATEGY
                </span>
                <span className={`font-mono text-[10px] ${tone}`}>
                  {signal}
                </span>
                <span className="font-mono text-slate-400">
                  conf {Math.round(item.confidence * 100)}%
                </span>
              </div>
              <div className="text-slate-200">
                <span className="font-mono text-slate-400">{item.strategy_name}</span>{" "}
                {item.reasoning}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}

