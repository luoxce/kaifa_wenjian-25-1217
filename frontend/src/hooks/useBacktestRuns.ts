import { useCallback, useMemo, useState } from "react";

import type { BacktestRun } from "@/types/schema";

interface BacktestRunsState {
  runs: BacktestRun[];
  selectedRun?: BacktestRun;
  comparedRuns: BacktestRun[];
  addRun: (run: BacktestRun) => void;
  removeRun: (id: number) => void;
  selectRun: (id: number) => void;
  toggleCompare: (id: number) => void;
  clearCompare: () => void;
}

export const useBacktestRuns = (): BacktestRunsState => {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [compareIds, setCompareIds] = useState<number[]>([]);

  const addRun = useCallback((run: BacktestRun) => {
    setRuns((prev) => {
      const exists = prev.find((item) => item.id === run.id);
      if (exists) {
        return prev.map((item) => (item.id === run.id ? run : item));
      }
      return [run, ...prev];
    });
    setSelectedId(run.id);
  }, []);

  const removeRun = useCallback((id: number) => {
    setRuns((prev) => prev.filter((run) => run.id !== id));
    setCompareIds((prev) => prev.filter((runId) => runId !== id));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const selectRun = useCallback((id: number) => {
    setSelectedId(id);
  }, []);

  const toggleCompare = useCallback((id: number) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((runId) => runId !== id);
      }
      if (prev.length >= 3) {
        return prev;
      }
      return [...prev, id];
    });
  }, []);

  const clearCompare = useCallback(() => {
    setCompareIds([]);
  }, []);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedId),
    [runs, selectedId]
  );

  const comparedRuns = useMemo(
    () => runs.filter((run) => compareIds.includes(run.id)),
    [runs, compareIds]
  );

  return {
    runs,
    selectedRun,
    comparedRuns,
    addRun,
    removeRun,
    selectRun,
    toggleCompare,
    clearCompare,
  };
};
