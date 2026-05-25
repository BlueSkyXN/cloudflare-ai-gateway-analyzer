import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useFilters } from "@/store/filters";

export function useScopes() {
  return useQuery({ queryKey: ["scopes"], queryFn: api.scopes });
}

export function useAnalytics(limit = 500) {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["analytics", filters, limit],
    queryFn: () => api.analytics({ ...filters, limit }),
    enabled: !!filters.gateway_id,
  });
}

export function useFilterOptions() {
  const filters = useFilters((s) => s.buildOptionFilters());
  return useQuery({
    queryKey: ["analytics-filter-options", filters],
    queryFn: async () => {
      const data = await api.analytics({ ...filters, limit: 1 });
      return data.filter_options;
    },
    enabled: !!filters.gateway_id,
    staleTime: 30_000,
  });
}

export function useStatus() {
  const filters = useFilters((s) => ({
    account_id: s.scope?.account_id,
    gateway_id: s.scope?.gateway_id,
  }));
  return useQuery({
    queryKey: ["status", filters],
    queryFn: () => api.status(filters),
  });
}

export function useSyncRuns(limit = 20) {
  const filters = useFilters((s) => ({
    account_id: s.scope?.account_id,
    gateway_id: s.scope?.gateway_id,
    limit,
  }));
  return useQuery({ queryKey: ["sync-runs", filters], queryFn: () => api.syncRuns(filters) });
}

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: 3000,
  });
}

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: api.config });
}
