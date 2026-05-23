import type {
  AnalyticsFilters,
  ConfigResponse,
  ContextBucket,
  EventsResponse,
  InsightItem,
  ModelStats,
  ScopeItem,
  StatusResponse,
  SummaryResponse,
  SyncJobSnapshot,
  SyncRunSnapshot,
  SyncTriggerResponse,
  TimeseriesPoint,
} from "./types";

const API_BASE = "/api/v1";

function toQueryString(filters: AnalyticsFilters | undefined): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("cf-aigw-token");
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : detail;
    } catch (_) {
      // ignore JSON parse error
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  scopes: () => request<ScopeItem[]>("/scopes"),
  summary: (filters: AnalyticsFilters) =>
    request<SummaryResponse>(`/analytics/summary${toQueryString(filters)}`),
  timeseries: (filters: AnalyticsFilters) =>
    request<TimeseriesPoint[]>(`/analytics/timeseries${toQueryString(filters)}`),
  models: (filters: AnalyticsFilters) =>
    request<ModelStats[]>(`/analytics/models${toQueryString(filters)}`),
  contextBuckets: (filters: AnalyticsFilters) =>
    request<ContextBucket[]>(`/analytics/context-buckets${toQueryString(filters)}`),
  insights: (filters: AnalyticsFilters) =>
    request<InsightItem[]>(`/analytics/insights${toQueryString(filters)}`),
  events: (filters: AnalyticsFilters & { limit?: number }) =>
    request<EventsResponse>(`/events${toQueryString(filters)}`),
  status: (filters: { account_id?: string; gateway_id?: string }) =>
    request<StatusResponse>(`/status${toQueryString(filters)}`),
  config: () => request<ConfigResponse>("/config"),
  syncRuns: (filters: { account_id?: string; gateway_id?: string; limit?: number }) =>
    request<SyncRunSnapshot[]>(`/sync/runs${toQueryString(filters)}`),
  triggerSyncLogs: (body: Record<string, unknown>) =>
    request<SyncTriggerResponse>("/sync/logs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  triggerSyncUsage: (body: Record<string, unknown>) =>
    request<SyncTriggerResponse>("/sync/usage", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  jobs: () => request<SyncJobSnapshot[]>("/sync/jobs"),
  job: (jobId: string) => request<SyncJobSnapshot>(`/sync/jobs/${jobId}`),
};
