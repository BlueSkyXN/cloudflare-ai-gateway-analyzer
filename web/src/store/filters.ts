import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AnalyticsFilters, ScopeItem } from "@/api/types";

type FilterState = {
  scope: ScopeItem | null;
  timeRange: "all" | "24h" | "7d" | "30d";
  model: string | null;
  provider: string | null;
  successFilter: "all" | "success" | "failed";
  setScope: (scope: ScopeItem | null) => void;
  setTimeRange: (range: FilterState["timeRange"]) => void;
  setModel: (model: string | null) => void;
  setProvider: (provider: string | null) => void;
  setSuccessFilter: (value: FilterState["successFilter"]) => void;
  buildFilters: () => AnalyticsFilters;
};

function computeStart(range: FilterState["timeRange"]): string | undefined {
  if (range === "all") return undefined;
  const now = Date.now();
  const hours = range === "24h" ? 24 : range === "7d" ? 168 : 720;
  const startDate = new Date(now - hours * 60 * 60 * 1000);
  return startDate.toISOString();
}

export const useFilters = create<FilterState>()(
  persist(
    (set, get) => ({
      scope: null,
      timeRange: "all",
      model: null,
      provider: null,
      successFilter: "all",
      setScope: (scope) => set({ scope }),
      setTimeRange: (timeRange) => set({ timeRange }),
      setModel: (model) => set({ model }),
      setProvider: (provider) => set({ provider }),
      setSuccessFilter: (successFilter) => set({ successFilter }),
      buildFilters: () => {
        const { scope, timeRange, model, provider, successFilter } = get();
        const filters: AnalyticsFilters = {};
        if (scope) {
          filters.account_id = scope.account_id;
          filters.gateway_id = scope.gateway_id;
        }
        const start = computeStart(timeRange);
        if (start) filters.start_date = start;
        if (model) filters.model = model;
        if (provider) filters.provider = provider;
        if (successFilter === "success") filters.success = true;
        if (successFilter === "failed") filters.success = false;
        return filters;
      },
    }),
    { name: "cf-aigw-filters" }
  )
);
