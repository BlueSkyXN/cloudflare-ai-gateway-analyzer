export type ScopeItem = {
  account_id: string;
  gateway_id: string;
  name: string;
  logs: number;
  first_log_at: string | null;
  last_log_at: string | null;
};

export type SummaryResponse = {
  requests: number;
  success_count: number;
  failed_count: number;
  success_rate: number | null;
  models: number;
  providers: number;
  first_log_at: string | null;
  last_log_at: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  cache_ratio: number | null;
  avg_total_ms: number | null;
  p50_total_ms: number | null;
  p95_total_ms: number | null;
  p99_total_ms: number | null;
  avg_latency_ms: number | null;
  avg_output_tps: number | null;
  avg_visible_output_tps: number | null;
  usage_statuses: Record<string, number>;
};

export type TimeseriesPoint = {
  hour: string;
  requests: number;
  success_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  rpm: number;
  tpm: number;
  avg_total_ms: number | null;
  avg_latency_ms: number | null;
  avg_output_tps: number | null;
  avg_visible_output_tps: number | null;
};

export type ModelStats = {
  model: string;
  providers: string[];
  requests: number;
  success_count: number;
  success_rate: number | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  cache_ratio: number | null;
  tokens_per_request: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
  avg_total_ms: number | null;
  avg_output_tps: number | null;
  avg_visible_output_tps: number | null;
  p95_total_ms: number | null;
};

export type ContextBucket = {
  context_bucket: string;
  requests: number;
  success_count: number;
  success_rate: number | null;
  avg_input_tokens: number | null;
  avg_output_tokens: number | null;
  total_tokens: number;
  cached_tokens: number;
  cache_ratio: number | null;
  avg_total_ms: number | null;
  avg_output_tps: number | null;
  avg_visible_output_tps: number | null;
};

export type InsightItem = {
  level: "info" | "warning" | "danger";
  title: string;
  detail: string;
};

export type EventItem = {
  log_id: string;
  created_at: string | null;
  provider: string | null;
  model: string | null;
  model_type: string | null;
  success: boolean | null;
  cached: boolean | null;
  status_code: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cached_tokens: number | null;
  reasoning_tokens: number | null;
  usage_fetch_status: string | null;
  duration_ms: number | null;
  latency_ms: number | null;
  total_ms: number | null;
  generation_ms: number | null;
  output_tps: number | null;
  visible_output_tps: number | null;
};

export type EventsResponse = {
  events: EventItem[];
  count: number;
};

export type StatusResponse = {
  database: string;
  database_bytes: number;
  total_logs: number;
  first_log_at: string | null;
  last_log_at: string | null;
  usage_parsed: number;
  usage_no_usage: number;
  usage_failed: number;
  last_run: Record<string, unknown> | null;
};

export type SyncJobSnapshot = {
  job_id: string;
  status: "running" | "done" | "failed";
  mode: string;
  started_at: string;
  finished_at: string | null;
  logs_count: number;
  usage_fetched: number;
  usage_parsed: number;
  usage_no_usage: number;
  usage_failed: number;
  targets: number;
  error: string | null;
  run_id: number | null;
};

export type SyncTriggerResponse = {
  job_id: string;
  status: string;
  mode: string;
};

export type AnalyticsFilters = {
  account_id?: string;
  gateway_id?: string;
  start_date?: string;
  end_date?: string;
  provider?: string;
  model?: string;
  success?: boolean;
};

export type SyncRunSnapshot = {
  run_id: number;
  account_id: string | null;
  gateway_id: string | null;
  mode: string;
  params: Record<string, unknown>;
  logs_count: number;
  usage_fetched: number;
  usage_parsed: number;
  usage_no_usage: number;
  usage_failed: number;
  started_at: string;
  finished_at: string;
};

export type ConfigResponse = {
  cloudflare: {
    api_token: string | null;
    email: string | null;
    api_key: string | null;
    base_url: string;
    timeout: number;
    retries: number;
  };
  storage: {
    data_dir: string;
    db_filename: string;
  };
  sync: {
    per_page: number;
    log_throttle_ms: number;
    usage_workers: number;
    usage_batch_size: number;
    retry_failed: boolean;
  };
  control: {
    host: string;
    port: number;
    auth_token: string | null;
    expose_docs: boolean;
    cors_origins: string[];
    default_account_id: string | null;
    default_gateway_id: string | null;
  };
  logging: {
    level: string;
    format: string;
  };
};
