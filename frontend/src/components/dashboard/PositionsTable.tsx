import type { Position } from "@/types/schema";

interface PositionsTableProps {
  positions: Position[];
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  if (!positions.length) {
    return <div className="text-xs text-slate-500">No open positions.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead className="text-slate-500">
          <tr>
            <th className="px-2 py-1 text-left">Symbol</th>
            <th className="px-2 py-1 text-left">Side</th>
            <th className="px-2 py-1 text-right">Size</th>
            <th className="px-2 py-1 text-right">Entry</th>
            <th className="px-2 py-1 text-right">Mark</th>
            <th className="px-2 py-1 text-right">Value</th>
            <th className="px-2 py-1 text-right">PnL</th>
            <th className="px-2 py-1 text-right">PnL %</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => {
            const isPositive = pos.unrealized_pnl >= 0;
            const pnlClass = isPositive ? "text-[#00ff9d]" : "text-[#ff0055]";
            const pnlBg = isPositive ? "bg-[#00ff9d]/5" : "bg-[#ff0055]/5";
            const mark = pos.mark_price ?? pos.entry_price;
            const notional = Math.abs(pos.size * (mark ?? 0));
            const cost = Math.abs(pos.size * (pos.entry_price ?? 0));
            const pnlPct = cost > 0 ? (pos.unrealized_pnl / cost) * 100 : 0;
            const pnlPctText = `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%`;
            return (
              <tr
                key={`${pos.symbol}-${pos.side}`}
                className="border-b border-[#1f1f1f] last:border-0"
              >
                <td className="px-2 py-1">{pos.symbol}</td>
                <td className="px-2 py-1 capitalize">{pos.side}</td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.size.toFixed(4)}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.entry_price.toFixed(2)}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.mark_price?.toFixed?.(2) ?? "-"}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {notional.toFixed(2)}
                </td>
                <td className={`px-2 py-1 text-right font-mono ${pnlClass} ${pnlBg}`}>
                  {pos.unrealized_pnl.toFixed(2)}
                </td>
                <td className={`px-2 py-1 text-right font-mono ${pnlClass}`}>
                  {pnlPctText}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
