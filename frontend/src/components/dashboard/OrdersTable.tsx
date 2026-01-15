import type { Order } from "@/types/schema";

interface OrdersTableProps {
  orders: Order[];
}

export default function OrdersTable({ orders }: OrdersTableProps) {
  if (!orders.length) {
    return <div className="text-xs text-slate-500">No open orders.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead className="text-slate-500">
          <tr>
            <th className="px-2 py-1 text-left">Order</th>
            <th className="px-2 py-1 text-left">Side</th>
            <th className="px-2 py-1 text-right">Price</th>
            <th className="px-2 py-1 text-right">Filled</th>
            <th className="px-2 py-1 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => {
            const side = order.side?.toUpperCase?.() ?? order.side;
            const tone = side === "BUY" ? "text-[#00ff9d]" : "text-[#ff0055]";
            return (
              <tr
                key={order.order_id}
                className="border-b border-[#1f1f1f] last:border-0"
              >
                <td className="px-2 py-1 font-mono">{order.order_id}</td>
                <td className={`px-2 py-1 ${tone}`}>{side}</td>
                <td className="px-2 py-1 text-right font-mono">
                  {order.price?.toFixed?.(2) ?? "-"}
                </td>
                <td className="px-2 py-1 text-right font-mono">
                  {order.filled_amount?.toFixed?.(4) ?? "0.0000"}
                </td>
                <td className="px-2 py-1 text-right">{order.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

