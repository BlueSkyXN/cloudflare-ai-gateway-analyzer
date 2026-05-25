import { useEffect, useMemo } from "react";
import clsx from "clsx";

import { useFilterOptions, useScopes } from "@/hooks/queries";
import { useFilters, type TimeRange } from "@/store/filters";
import { formatInt, shortenId } from "@/utils/format";

const TIME_RANGES = [
  { value: "all", label: "全部" },
  { value: "24h", label: "24 小时" },
  { value: "7d", label: "7 天" },
  { value: "30d", label: "30 天" },
  { value: "custom", label: "自定义" },
] satisfies Array<{ value: TimeRange; label: string }>;

function toDatetimeLocalInput(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

export function ScopeSelector() {
  const { data: scopes, isLoading } = useScopes();
  const { data: filterOptions, isLoading: isLoadingOptions } = useFilterOptions();
  const scope = useFilters((s) => s.scope);
  const setScope = useFilters((s) => s.setScope);
  const timeRange = useFilters((s) => s.timeRange);
  const setTimeRange = useFilters((s) => s.setTimeRange);
  const customStart = useFilters((s) => s.customStart);
  const customEnd = useFilters((s) => s.customEnd);
  const setCustomRange = useFilters((s) => s.setCustomRange);
  const provider = useFilters((s) => s.provider);
  const model = useFilters((s) => s.model);
  const successFilter = useFilters((s) => s.successFilter);
  const setProvider = useFilters((s) => s.setProvider);
  const setModel = useFilters((s) => s.setModel);
  const setSuccessFilter = useFilters((s) => s.setSuccessFilter);

  useEffect(() => {
    if (!scope && scopes && scopes.length > 0) {
      setScope(scopes[0]);
    }
  }, [scope, scopes, setScope]);

  const providerOptions = filterOptions?.providers ?? [];
  const modelOptions = useMemo(() => {
    const models = filterOptions?.models ?? [];
    if (!provider) return models;
    return models.filter((item) => item.providers.includes(provider));
  }, [filterOptions?.models, provider]);

  useEffect(() => {
    if (!filterOptions || !model) return;
    if (!modelOptions.some((item) => item.model === model)) {
      setModel(null);
    }
  }, [filterOptions, model, modelOptions, setModel]);

  const selectTimeRange = (range: TimeRange) => {
    if (range !== "custom") {
      setTimeRange(range);
      return;
    }
    if (customStart || customEnd) {
      setTimeRange("custom");
      return;
    }
    const end = scope?.last_log_at ? new Date(scope.last_log_at) : new Date();
    const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
    setCustomRange(toDatetimeLocalInput(start), toDatetimeLocalInput(end));
  };

  const customInvalid =
    timeRange === "custom" &&
    customStart &&
    customEnd &&
    new Date(customStart).getTime() > new Date(customEnd).getTime();
  const hasSecondaryFilters = Boolean(provider || model || successFilter !== "all");

  return (
    <div className="grid grid-cols-1 gap-3 rounded-lg border border-line bg-bg-panel p-3 shadow-sm xl:grid-cols-[minmax(280px,0.8fr)_minmax(420px,1.2fr)]">
      <label className="flex min-w-0 flex-col gap-1 text-sm lg:min-w-[320px]">
        <span className="text-xs font-medium text-text-dim">网关范围</span>
        <select
          className="field w-full"
          value={scope ? `${scope.account_id}/${scope.gateway_id}` : ""}
          disabled={isLoading || !scopes || scopes.length === 0}
          onChange={(e) => {
            const target = scopes?.find(
              (s) => `${s.account_id}/${s.gateway_id}` === e.target.value
            );
            if (target) setScope(target);
          }}
        >
          {!scopes || scopes.length === 0 ? (
            <option value="">暂无数据</option>
          ) : (
            scopes.map((s) => (
              <option key={`${s.account_id}/${s.gateway_id}`} value={`${s.account_id}/${s.gateway_id}`}>
                {s.name} · {shortenId(s.account_id)} · {s.logs.toLocaleString("zh-CN")} 条
              </option>
            ))
          )}
        </select>
      </label>

      <div className="flex flex-1 flex-col gap-2">
        <span className="text-xs font-medium text-text-dim">时间范围</span>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-md border border-line bg-bg-subtle p-0.5">
            {TIME_RANGES.map((range) => (
              <button
                key={range.value}
                type="button"
                onClick={() => selectTimeRange(range.value)}
                className={clsx(
                  "px-2.5 py-1.5 text-sm rounded whitespace-nowrap transition-colors",
                  timeRange === range.value
                    ? "bg-bg-panel text-text shadow-sm"
                    : "text-text-dim hover:text-text"
                )}
              >
                {range.label}
              </button>
            ))}
          </div>
          {timeRange === "custom" && (
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1 text-xs text-text-dim">
                开始
                <input
                  type="datetime-local"
                  className="field"
                  value={customStart}
                  onChange={(e) => setCustomRange(e.target.value, customEnd)}
                />
              </label>
              <label className="flex items-center gap-1 text-xs text-text-dim">
                结束
                <input
                  type="datetime-local"
                  className="field"
                  value={customEnd}
                  onChange={(e) => setCustomRange(customStart, e.target.value)}
                />
              </label>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setCustomRange("", "");
                  setTimeRange("all");
                }}
              >
                清空
              </button>
            </div>
          )}
        </div>
        {customInvalid && <span className="text-xs text-danger">结束时间不能早于开始时间。</span>}
      </div>

      <div className="flex flex-col gap-2 xl:col-span-2">
        <span className="text-xs font-medium text-text-dim">维度筛选</span>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_160px_auto] md:items-end">
          <label className="flex min-w-0 flex-col gap-1 text-sm">
            <span className="text-xs text-text-dim">渠道</span>
            <select
              className="field w-full"
              value={provider ?? ""}
              disabled={!scope || isLoadingOptions || providerOptions.length === 0}
              onChange={(event) => setProvider(event.target.value || null)}
            >
              <option value="">全部渠道</option>
              {providerOptions.map((item) => (
                <option key={item.provider} value={item.provider}>
                  {item.provider} · {formatInt(item.requests)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex min-w-0 flex-col gap-1 text-sm">
            <span className="text-xs text-text-dim">模型</span>
            <select
              className="field w-full"
              value={model ?? ""}
              disabled={!scope || isLoadingOptions || modelOptions.length === 0}
              onChange={(event) => setModel(event.target.value || null)}
            >
              <option value="">全部模型</option>
              {modelOptions.map((item) => (
                <option key={item.model} value={item.model}>
                  {item.model} · {formatInt(item.requests)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex min-w-0 flex-col gap-1 text-sm">
            <span className="text-xs text-text-dim">结果</span>
            <select
              className="field w-full"
              value={successFilter}
              onChange={(event) =>
                setSuccessFilter(event.target.value as "all" | "success" | "failed")
              }
            >
              <option value="all">全部</option>
              <option value="success">成功</option>
              <option value="failed">失败</option>
            </select>
          </label>

          <button
            type="button"
            className="btn h-[34px]"
            disabled={!hasSecondaryFilters}
            onClick={() => {
              setProvider(null);
              setModel(null);
              setSuccessFilter("all");
            }}
          >
            清空筛选
          </button>
        </div>
      </div>
    </div>
  );
}
