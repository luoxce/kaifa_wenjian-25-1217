import type { Position } from "@/types/schema";

interface PositionsTableProps {
  positions: Position[];
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  if (!positions.length) {
    return <div className="text-xs text-slate-400">No open positions.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="text-slate-400">
          <tr>
            <th className="px-2 py-1 text-left">Symbol</th>
            <th className="px-2 py-1 text-left">Side</th>
            <th className="px-2 py-1 text-right">Size</th>
            <th className="px-2 py-1 text-right">Entry</th>
            <th className="px-2 py-1 text-right">Mark</th>
            <th className="px-2 py-1 text-right">PnL</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => {
            const pnlClass =
              pos.unrealized_pnl >= 0 ? "text-emerald-400" : "text-rose-400";
            return (
              <tr key={`${pos.symbol}-${pos.side}`}>
                <td className="px-2 py-1">{pos.symbol}</td>
                <td className="px-2 py-1 capitalize">{pos.side}</td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.size.toFixed(4)}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.entry_price.toFixed(2)}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {pos.mark_price.toFixed(2)}
                </td>
                <td className={`px-2 py-1 text-right font-mono ${pnlClass}`}>
                  {pos.unrealized_pnl.toFixed(2)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
