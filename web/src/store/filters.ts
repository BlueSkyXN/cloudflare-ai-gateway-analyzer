import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AnalyticsFilters, ScopeItem } from "@/api/types";

export type TimeRange = "all" | "24h" | "7d" | "30d" | "custom";
export type TimeseriesBucketHours = 1 | 4 | 8 | 12 | 24;

type FilterState = {
  scope: ScopeItem | null;
  timeRange: TimeRange;
  customStart: string;
  customEnd: string;
  model: string | null;
  provider: string | null;
  successFilter: "all" | "success" | "failed";
  timeseriesBucketHours: TimeseriesBucketHours;
  setScope: (scope: ScopeItem | null) => void;
  setTimeRange: (range: TimeRange) => void;
  setTimeseriesBucketHours: (hours: TimeseriesBucketHours) => void;
  setCustomRange: (start: string, end: string) => void;
  setModel: (model: string | null) => void;
  setProvider: (provider: string | null) => void;
  setSuccessFilter: (value: FilterState["successFilter"]) => void;
  buildFilters: () => AnalyticsFilters;
  buildOptionFilters: () => AnalyticsFilters;
};

function computeTimeRange(
  range: TimeRange,
  anchorIso?: string | null
): { start?: string; end?: string } {
  if (range === "all" || range === "custom") return {};
  const anchor = anchorIso ? new Date(anchorIso).getTime() : Number.NaN;
  const endDate = new Date(Number.isNaN(anchor) ? Date.now() : anchor);
  const hours = range === "24h" ? 24 : range === "7d" ? 168 : 720;
  const startDate = new Date(endDate.getTime() - hours * 60 * 60 * 1000);
  return { start: startDate.toISOString(), end: endDate.toISOString() };
}

function toUtcIso(value: string, boundary: "start" | "end" = "start"): string | undefined {
  if (!value) return undefined;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  if (boundary === "end" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    parsed.setMilliseconds(parsed.getMilliseconds() + 60_000 - 1);
  }
  return parsed.toISOString();
}

export const useFilters = create<FilterState>()(
  persist(
    (set, get) => ({
      scope: null,
      timeRange: "all",
      customStart: "",
      customEnd: "",
      model: null,
      provider: null,
      successFilter: "all",
      timeseriesBucketHours: 1,
      setScope: (scope) => set({ scope }),
      setTimeRange: (timeRange) => set({ timeRange }),
      setTimeseriesBucketHours: (timeseriesBucketHours) => set({ timeseriesBucketHours }),
      setCustomRange: (customStart, customEnd) =>
        set({ customStart, customEnd, timeRange: "custom" }),
      setModel: (model) => set({ model }),
      setProvider: (provider) => set({ provider }),
      setSuccessFilter: (successFilter) => set({ successFilter }),
      buildFilters: () => {
        const {
          scope,
          timeRange,
          customStart,
          customEnd,
          model,
          provider,
          successFilter,
          timeseriesBucketHours,
        } = get();
        const filters: AnalyticsFilters = {};
        if (scope) {
          filters.account_id = scope.account_id;
          filters.gateway_id = scope.gateway_id;
        }
        const { start, end } =
          timeRange === "custom"
            ? { start: toUtcIso(customStart), end: toUtcIso(customEnd, "end") }
            : computeTimeRange(timeRange, scope?.last_log_at);
        if (start) filters.start_date = start;
        if (end) filters.end_date = end;
        filters.timeseries_bucket_hours = timeseriesBucketHours;
        if (model) filters.model = model;
        if (provider) filters.provider = provider;
        if (successFilter === "success") filters.success = true;
        if (successFilter === "failed") filters.success = false;
        return filters;
      },
      buildOptionFilters: () => {
        const { scope, timeRange, customStart, customEnd, successFilter } = get();
        const filters: AnalyticsFilters = {};
        if (scope) {
          filters.account_id = scope.account_id;
          filters.gateway_id = scope.gateway_id;
        }
        const { start, end } =
          timeRange === "custom"
            ? { start: toUtcIso(customStart), end: toUtcIso(customEnd, "end") }
            : computeTimeRange(timeRange, scope?.last_log_at);
        if (start) filters.start_date = start;
        if (end) filters.end_date = end;
        if (successFilter === "success") filters.success = true;
        if (successFilter === "failed") filters.success = false;
        return filters;
      },
    }),
    { name: "cf-aigw-filters" }
  )
);
