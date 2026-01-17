import type { Trade } from "@/types/schema";

interface TradesTableProps {
  trades: Trade[];
}

const formatTs = (value: number) => {
  const ts = value > 1_000_000_000_000 ? value : value * 1000;
  return new Date(ts).toLocaleString(undefined, { hour12: false });
};

export default function TradesTable({ trades }: TradesTableProps) {
  if (!trades.length) {
    return <div className="text-xs text-slate-500">No trades recorded.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead className="text-slate-500">
          <tr>
            <th className="px-2 py-1 text-left">Time</th>
            <th className="px-2 py-1 text-left">Side</th>
            <th className="px-2 py-1 text-right">Price</th>
            <th className="px-2 py-1 text-right">Amount</th>
            <th className="px-2 py-1 text-right">Fee</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, idx) => {
            const side = trade.side?.toUpperCase?.() ?? trade.side;
            const tone = side === "BUY" ? "text-[#00ff9d]" : "text-[#ff0055]";
            return (
              <tr
                key={`${trade.symbol}-${trade.timestamp}-${idx}`}
                className="border-b border-[#1f1f1f] last:border-0"
              >
                <td className="px-2 py-1 font-mono">
                  {formatTs(trade.timestamp)}
                </td>
                <td className={`px-2 py-1 ${tone}`}>{side}</td>
                <td className="px-2 py-1 text-right font-mono">
                  {trade.price?.toFixed?.(2) ?? "-"}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {trade.amount?.toFixed?.(4) ?? "-"}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {trade.fee?.toFixed?.(4) ?? "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
