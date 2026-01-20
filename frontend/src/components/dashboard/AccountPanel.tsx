import type { AccountSummary, Position } from "@/types/schema";

interface AccountPanelProps {
  account: AccountSummary;
  positions: Position[];
  symbol: string;
  lastPrice?: number;
}

const parseBaseAsset = (symbol: string) => {
  if (!symbol) return "";
  const primary = symbol.split("/")[0] ?? symbol;
  return primary.split("-")[0] ?? primary;
};

const formatSigned = (value: number, digits = 2) => {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
};

export default function AccountPanel({
  account,
  positions,
  symbol,
  lastPrice,
}: AccountPanelProps) {
  const balances = account.balances ?? [];
  const baseAsset = parseBaseAsset(symbol);
  const usdtBalance = balances.find((item) => item.asset === "USDT");
  const available =
    usdtBalance?.free ??
    balances.reduce((sum, item) => sum + (item.free ?? 0), 0);
  const used =
    usdtBalance?.used ??
    balances.reduce((sum, item) => sum + (item.used ?? 0), 0);
  const totalEquity = account.total_equity ?? 0;

  const positionValue = positions.reduce((sum, pos) => {
    const mark = pos.mark_price ?? pos.entry_price ?? 0;
    return sum + Math.abs(pos.size * mark);
  }, 0);
  const positionCost = positions.reduce(
    (sum, pos) => sum + Math.abs(pos.size * (pos.entry_price ?? 0)),
    0
  );
  const positionPnl = positions.reduce(
    (sum, pos) => sum + (pos.unrealized_pnl ?? 0),
    0
  );
  const positionPnlPct =
    positionCost > 0 ? (positionPnl / positionCost) * 100 : 0;

  const totalPnl = (account.unrealized_pnl ?? 0) + (account.daily_pnl ?? 0);
  const totalPnlPct = totalEquity > 0 ? (totalPnl / totalEquity) * 100 : 0;
  const pnlTone = totalPnl >= 0 ? "text-[#00ff9d]" : "text-[#ff0055]";
  const positionPnlTone = positionPnl >= 0 ? "text-[#00ff9d]" : "text-[#ff0055]";

  const sortedBalances = [...balances].sort((a, b) => {
    if (a.asset === "USDT") return -1;
    if (b.asset === "USDT") return 1;
    return a.asset.localeCompare(b.asset);
  });

  const estimateValue = (asset: string, total: number) => {
    if (asset === "USDT") return total;
    if (asset === baseAsset && lastPrice && lastPrice > 0) {
      return total * lastPrice;
    }
    return null;
  };

  return (
    <section className="rounded-lg border border-[#27272a] bg-[#0a0a0a]/80 p-3">
      <div className="mb-3 flex items-center justify-between text-[11px] text-slate-400">
        <span>Account Snapshot</span>
        <span className="font-mono text-slate-300">{symbol}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
        <Metric label="Total Assets (USDT)" value={`${totalEquity.toFixed(2)}`} />
        <Metric label="Available (USDT)" value={`${available.toFixed(2)}`} />
        <Metric label="Used Margin (USDT)" value={`${used.toFixed(2)}`} />
        <Metric label="Position Value (USDT)" value={`${positionValue.toFixed(2)}`} />
        <Metric
          label="Position PnL"
          value={formatSigned(positionPnl)}
          sub={`${formatSigned(positionPnlPct, 2)}%`}
          tone={positionPnlTone}
        />
        <Metric
          label="Total PnL"
          value={formatSigned(totalPnl)}
          sub={`${formatSigned(totalPnlPct, 2)}%`}
          tone={pnlTone}
        />
      </div>

      <div className="mt-3 rounded-md border border-[#1f1f1f] bg-[#050505]/70">
        <div className="flex items-center justify-between border-b border-[#1f1f1f] px-3 py-2 text-[11px] text-slate-400">
          <span>Balances</span>
          <span className="text-[10px] text-slate-500">
            Base pricing: {baseAsset}/USDT
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Asset</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-right">Available</th>
                <th className="px-3 py-2 text-right">In Use</th>
                <th className="px-3 py-2 text-right">Est. Value (USDT)</th>
              </tr>
            </thead>
            <tbody>
              {sortedBalances.map((item) => {
                const estimate = estimateValue(item.asset, item.total);
                return (
                  <tr
                    key={item.asset}
                    className="border-b border-[#1f1f1f] last:border-0"
                  >
                    <td className="px-3 py-2 font-mono text-slate-200">
                      {item.asset}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {item.total.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {item.free.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {item.used.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-slate-200">
                      {estimate === null ? "--" : estimate.toFixed(2)}
                    </td>
                  </tr>
                );
              })}
              {!sortedBalances.length && (
                <tr>
                  <td className="px-3 py-3 text-left text-slate-500" colSpan={5}>
                    No balances synced yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#1f1f1f] bg-[#050505]/70 px-3 py-2">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
            Account Value (USDT)
          </div>
          <div className="text-lg font-mono text-slate-100">
            {totalEquity.toFixed(2)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
            Total PnL
          </div>
          <div className={`text-lg font-mono ${pnlTone}`}>
            {formatSigned(totalPnl)} ({formatSigned(totalPnlPct, 2)}%)
          </div>
        </div>
      </div>
    </section>
  );
}

interface MetricProps {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}

function Metric({ label, value, sub, tone }: MetricProps) {
  const textTone = tone ?? "text-slate-100";
  return (
    <div className="rounded-md border border-[#1f1f1f] bg-[#050505]/70 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
        {label}
      </div>
      <div className={`mt-1 font-mono text-sm ${textTone}`}>{value}</div>
      {sub && <div className={`text-[11px] ${textTone}`}>{sub}</div>}
    </div>
  );
}
