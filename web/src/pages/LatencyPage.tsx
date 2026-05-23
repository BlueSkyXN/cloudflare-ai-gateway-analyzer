import { useSummary, useTimeseries } from "@/hooks/queries";
import { Chart } from "@/components/Chart";
import { KpiCard } from "@/components/KpiCard";
import { formatDuration } from "@/utils/format";

export function LatencyPage() {
  const { data: summary } = useSummary();
  const { data: timeseries } = useTimeseries();
  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Avg Total" value={formatDuration(summary?.avg_total_ms)} />
        <KpiCard label="P50" value={formatDuration(summary?.p50_total_ms)} />
        <KpiCard label="P95" value={formatDuration(summary?.p95_total_ms)} />
        <KpiCard label="P99" value={formatDuration(summary?.p99_total_ms)} />
      </section>

      <section className="panel-lg">
        <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Latency by Hour</h2>
        <Chart
          option={{
            legend: { data: ["Avg Total", "Avg Latency"], top: 0 },
            xAxis: { type: "category", data: (timeseries ?? []).map((p) => p.hour) },
            yAxis: { type: "value", name: "ms" },
            series: [
              {
                name: "Avg Total",
                type: "line",
                smooth: true,
                data: (timeseries ?? []).map((p) => p.avg_total_ms?.toFixed(0) ?? null),
                lineStyle: { color: "#f97316" },
                itemStyle: { color: "#f97316" },
              },
              {
                name: "Avg Latency",
                type: "line",
                smooth: true,
                data: (timeseries ?? []).map((p) => p.avg_latency_ms?.toFixed(0) ?? null),
                lineStyle: { color: "#9aa4b8" },
                itemStyle: { color: "#9aa4b8" },
              },
            ],
          }}
        />
      </section>

      <section className="panel-lg">
        <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Output TPS by Hour</h2>
        <Chart
          option={{
            legend: { data: ["Avg TPS", "Visible TPS"], top: 0 },
            xAxis: { type: "category", data: (timeseries ?? []).map((p) => p.hour) },
            yAxis: { type: "value" },
            series: [
              {
                name: "Avg TPS",
                type: "line",
                smooth: true,
                data: (timeseries ?? []).map((p) => p.avg_output_tps?.toFixed(2) ?? null),
                lineStyle: { color: "#22c55e" },
                itemStyle: { color: "#22c55e" },
              },
              {
                name: "Visible TPS",
                type: "line",
                smooth: true,
                data: (timeseries ?? []).map((p) => p.avg_visible_output_tps?.toFixed(2) ?? null),
                lineStyle: { color: "#f59e0b" },
                itemStyle: { color: "#f59e0b" },
              },
            ],
          }}
        />
      </section>
    </div>
  );
}
