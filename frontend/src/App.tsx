import DashboardLayout from "@/components/dashboard/DashboardLayout";
import BacktestWorkspace from "@/pages/backtest/BacktestWorkspace";
import DataMonitor from "@/pages/DataMonitor";

export default function App() {
  const path = window.location.pathname;

  if (path.startsWith("/backtest")) {
    return <BacktestWorkspace />;
  }

  if (path.startsWith("/data-monitor") || path.startsWith("/admin/data")) {
    return <DataMonitor />;
  }

  return <DashboardLayout />;
}
