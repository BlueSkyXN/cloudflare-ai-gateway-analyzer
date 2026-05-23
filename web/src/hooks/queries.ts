import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useFilters } from "@/store/filters";

export function useScopes() {
  return useQuery({ queryKey: ["scopes"], queryFn: api.scopes });
}

export function useSummary() {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["summary", filters],
    queryFn: () => api.summary(filters),
    enabled: !!filters.gateway_id,
  });
}

export function useTimeseries() {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["timeseries", filters],
    queryFn: () => api.timeseries(filters),
    enabled: !!filters.gateway_id,
  });
}

export function useModelStats() {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["models", filters],
    queryFn: () => api.models(filters),
    enabled: !!filters.gateway_id,
  });
}

export function useContextBuckets() {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["context-buckets", filters],
    queryFn: () => api.contextBuckets(filters),
    enabled: !!filters.gateway_id,
  });
}

export function useInsights() {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["insights", filters],
    queryFn: () => api.insights(filters),
    enabled: !!filters.gateway_id,
  });
}

export function useEvents(limit = 500) {
  const filters = useFilters((s) => s.buildFilters());
  return useQuery({
    queryKey: ["events", filters, limit],
    queryFn: () => api.events({ ...filters, limit }),
    enabled: !!filters.gateway_id,
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
