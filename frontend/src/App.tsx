import DashboardLayout from "@/components/dashboard/DashboardLayout";
import { useMarketData } from "@/hooks/useMarketData";

export default function App() {
  const { data, isLoading } = useMarketData();

  if (isLoading || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050505] text-slate-400">
        Loading dashboard...
      </div>
    );
  }

  return <DashboardLayout data={data} />;
}
