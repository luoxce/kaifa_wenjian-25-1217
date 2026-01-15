import type { StrategyDecision } from "@/types/schema";

interface DecisionLogProps {
  decisions: StrategyDecision[];
}

const toTime = (ts: number) => new Date(ts).toLocaleTimeString();

export default function DecisionLog({ decisions }: DecisionLogProps) {
  if (!decisions.length) {
    return <div className="text-xs text-slate-400">No decisions yet.</div>;
  }
  return (
    <div className="space-y-2 text-xs">
      {decisions.map((decision) => (
        <div
          key={`${decision.strategy_name}-${decision.timestamp}`}
          className="rounded-md border border-slate-800 bg-slate-900/60 p-2"
        >
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>{decision.strategy_name}</span>
            <span className="font-mono">{toTime(decision.timestamp)}</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] uppercase">
              {decision.signal}
            </span>
            <span className="text-[11px] text-slate-400">
              Conf: {(decision.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-300">
            {decision.reasoning}
          </p>
        </div>
      ))}
    </div>
  );
}
