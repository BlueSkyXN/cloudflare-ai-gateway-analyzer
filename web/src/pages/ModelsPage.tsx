import { useContextBuckets, useModelStats } from "@/hooks/queries";
import { Chart } from "@/components/Chart";
import { formatDuration, formatFloat, formatInt, formatPercent } from "@/utils/format";

export function ModelsPage() {
  const { data: models } = useModelStats();
  const { data: buckets } = useContextBuckets();

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="panel-lg">
          <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Model Requests · Avg TPS</h2>
          <Chart
            option={{
              legend: { data: ["Requests", "Avg TPS"], top: 0 },
              xAxis: { type: "category", data: (models ?? []).slice(0, 12).map((m) => m.model) },
              yAxis: [
                { type: "value", name: "Requests" },
                { type: "value", name: "TPS", position: "right" },
              ],
              series: [
                {
                  name: "Requests",
                  type: "bar",
                  data: (models ?? []).slice(0, 12).map((m) => m.requests),
                  itemStyle: { color: "#f97316" },
                },
                {
                  name: "Avg TPS",
                  type: "line",
                  yAxisIndex: 1,
                  data: (models ?? []).slice(0, 12).map((m) => (m.avg_output_tps ?? 0).toFixed(2)),
                  lineStyle: { color: "#22c55e" },
                  itemStyle: { color: "#22c55e" },
                },
              ],
            }}
          />
        </div>
        <div className="panel-lg">
          <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Context Length vs TPS</h2>
          <Chart
            option={{
              xAxis: { type: "value", name: "Avg Input Tokens" },
              yAxis: { type: "value", name: "Avg Output TPS" },
              series: [
                {
                  type: "scatter",
                  symbolSize: (data: number[]) => Math.sqrt(data[2]) + 6,
                  data: (buckets ?? [])
                    .filter((b) => b.avg_input_tokens != null)
                    .map((b) => [
                      b.avg_input_tokens,
                      b.avg_output_tps ?? 0,
                      b.requests,
                      b.context_bucket,
                    ]),
                  label: {
                    show: true,
                    position: "right",
                    formatter: (param: { data: [number, number, number, string] }) =>
                      param.data[3],
                    color: "#9aa4b8",
                  },
                  itemStyle: { color: "#f97316" },
                },
              ],
            }}
          />
        </div>
      </section>

      <section className="panel-lg">
        <h2 className="text-sm uppercase tracking-wider text-text-dim mb-3">Model Comparison</h2>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>Model</th>
                <th>Providers</th>
                <th>Requests</th>
                <th>Success</th>
                <th>Tokens</th>
                <th>Cache</th>
                <th>Avg Latency</th>
                <th>P95</th>
                <th>Avg TPS</th>
                <th>Visible TPS</th>
              </tr>
            </thead>
            <tbody>
              {(models ?? []).map((m) => (
                <tr key={m.model}>
                  <td className="font-medium">{m.model}</td>
                  <td className="text-text-dim">{m.providers.join(", ") || "-"}</td>
                  <td>{formatInt(m.requests)}</td>
                  <td>{formatPercent(m.success_rate)}</td>
                  <td>{formatInt(m.total_tokens)}</td>
                  <td>{formatPercent(m.cache_ratio)}</td>
                  <td>{formatDuration(m.avg_total_ms)}</td>
                  <td>{formatDuration(m.p95_total_ms)}</td>
                  <td>{formatFloat(m.avg_output_tps)}</td>
                  <td>{formatFloat(m.avg_visible_output_tps)}</td>
                </tr>
              ))}
              {(models ?? []).length === 0 && (
                <tr>
                  <td colSpan={10} className="text-center text-text-dim py-6">
                    No model data.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel-lg">
        <h2 className="text-sm uppercase tracking-wider text-text-dim mb-3">Context Buckets</h2>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Requests</th>
                <th>Success</th>
                <th>Avg Input</th>
                <th>Avg Output</th>
                <th>Cache</th>
                <th>Avg Latency</th>
                <th>Avg TPS</th>
              </tr>
            </thead>
            <tbody>
              {(buckets ?? []).map((b) => (
                <tr key={b.context_bucket}>
                  <td className="font-medium">{b.context_bucket}</td>
                  <td>{formatInt(b.requests)}</td>
                  <td>{formatPercent(b.success_rate)}</td>
                  <td>{formatFloat(b.avg_input_tokens, 0)}</td>
                  <td>{formatFloat(b.avg_output_tokens, 0)}</td>
                  <td>{formatPercent(b.cache_ratio)}</td>
                  <td>{formatDuration(b.avg_total_ms)}</td>
                  <td>{formatFloat(b.avg_output_tps)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
