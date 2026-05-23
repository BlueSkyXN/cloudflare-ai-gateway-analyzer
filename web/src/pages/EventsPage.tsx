import clsx from "clsx";

import { useEvents } from "@/hooks/queries";
import { formatDuration, formatFloat, formatInt } from "@/utils/format";

export function EventsPage() {
  const { data, isLoading } = useEvents(500);
  const events = data?.events ?? [];

  return (
    <section className="panel-lg">
      <header className="flex items-center justify-between mb-3">
        <h2 className="text-sm uppercase tracking-wider text-text-dim">Recent Events</h2>
        <span className="text-xs text-text-dim">
          {isLoading ? "loading…" : `${data?.count ?? 0} rows (capped at 500)`}
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="compact">
          <thead>
            <tr>
              <th>Created</th>
              <th>Provider</th>
              <th>Model</th>
              <th>Status</th>
              <th>Input</th>
              <th>Output</th>
              <th>Cached</th>
              <th>Reasoning</th>
              <th>Total</th>
              <th>Total ms</th>
              <th>TPS</th>
              <th>Usage</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.log_id}>
                <td className="font-mono text-xs">{event.created_at?.slice(0, 19) ?? "-"}</td>
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
                    {event.success === null ? "-" : event.success ? "ok" : "fail"}
                  </span>
                </td>
                <td>{formatInt(event.input_tokens)}</td>
                <td>{formatInt(event.output_tokens)}</td>
                <td>{formatInt(event.cached_tokens)}</td>
                <td>{formatInt(event.reasoning_tokens)}</td>
                <td>{formatInt(event.total_tokens)}</td>
                <td>{formatDuration(event.total_ms)}</td>
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
                    {event.usage_fetch_status ?? "-"}
                  </span>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={12} className="text-center text-text-dim py-6">
                  No events.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
