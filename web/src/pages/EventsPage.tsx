import { useState } from "react";
import clsx from "clsx";

import { useAnalytics } from "@/hooks/queries";
import { formatDateTime, formatDuration, formatFloat, formatInt } from "@/utils/format";

const EVENT_LIMITS = [100, 200, 500];

function formatUsageStatus(value: string | null): string {
  if (value === "parsed") return "已解析";
  if (value === "failed") return "失败";
  if (value === "no_usage") return "无 usage";
  return value ?? "-";
}

export function EventsPage() {
  const [limit, setLimit] = useState(200);
  const { data, isLoading } = useAnalytics(limit);
  const events = data?.events ?? [];

  return (
    <section className="panel-lg">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-medium text-text-dim">近期事件</h2>
          <span className="text-xs text-text-dim">
            {isLoading ? "加载中..." : `${formatInt(events.length)} 行，当前上限 ${limit}`}
          </span>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-dim">
          行数
          <select
            className="field"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {EVENT_LIMITS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </header>
      <div className="overflow-x-auto">
        <table className="compact">
          <thead>
            <tr>
              <th>时间</th>
              <th>渠道</th>
              <th>模型</th>
              <th>状态</th>
              <th>输入</th>
              <th>输出</th>
              <th>总计</th>
              <th>总耗时</th>
              <th>输出时间</th>
              <th>TPS</th>
              <th>usage</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.log_id}>
                <td className="font-mono text-xs whitespace-nowrap">
                  {formatDateTime(event.created_at)}
                </td>
                <td>{event.provider ?? "-"}</td>
                <td className="font-medium">{event.model ?? "-"}</td>
                <td>
                  <span
                    className={clsx(
                      event.success === false && "chip-danger",
                      event.success === true && "chip-success",
                      event.success === null && "chip"
                    )}
                  >
                    {event.success === null ? "-" : event.success ? "成功" : "失败"}
                  </span>
                </td>
                <td>{formatInt(event.input_tokens)}</td>
                <td>{formatInt(event.output_tokens)}</td>
                <td>{formatInt(event.total_tokens)}</td>
                <td>{formatDuration(event.total_ms)}</td>
                <td>{formatDuration(event.generation_ms)}</td>
                <td>{formatFloat(event.output_tps)}</td>
                <td>
                  <span
                    className={clsx(
                      event.usage_fetch_status === "parsed" && "chip-success",
                      event.usage_fetch_status === "failed" && "chip-danger",
                      event.usage_fetch_status === "no_usage" && "chip-warning",
                      !event.usage_fetch_status && "chip"
                    )}
                  >
                    {formatUsageStatus(event.usage_fetch_status)}
                  </span>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={11} className="text-center text-text-dim py-6">
                  暂无事件。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
