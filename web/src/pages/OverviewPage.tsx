import { useInsights, useSummary, useTimeseries } from "@/hooks/queries";
import { formatDuration, formatFloat, formatInt, formatPercent } from "@/utils/format";
import { KpiCard } from "@/components/KpiCard";
import { Chart } from "@/components/Chart";
import { InsightsList } from "@/components/InsightsList";

export function OverviewPage() {
  const { data: summary } = useSummary();
  const { data: insights } = useInsights();
  const { data: timeseries } = useTimeseries();

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label="Requests" value={formatInt(summary?.requests)} />
        <KpiCard label="Success" value={formatPercent(summary?.success_rate)} hint={`${formatInt(summary?.success_count)} ok`} />
        <KpiCard label="Total Tokens" value={formatInt(summary?.total_tokens)} />
        <KpiCard label="Cache Ratio" value={formatPercent(summary?.cache_ratio)} />
        <KpiCard label="Avg TPS" value={formatFloat(summary?.avg_output_tps)} />
        <KpiCard label="Input Tokens" value={formatInt(summary?.input_tokens)} />
        <KpiCard label="Output Tokens" value={formatInt(summary?.output_tokens)} />
        <KpiCard label="Reasoning Tokens" value={formatInt(summary?.reasoning_tokens)} />
        <KpiCard label="Avg Latency" value={formatDuration(summary?.avg_total_ms)} />
        <KpiCard label="P95 Latency" value={formatDuration(summary?.p95_total_ms)} />
      </section>

      <section className="panel-lg">
        <h2 className="text-sm uppercase tracking-wider text-text-dim mb-3">Insights</h2>
        <InsightsList items={insights} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="panel-lg">
          <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Hourly Requests</h2>
          <Chart
            option={{
              xAxis: { type: "category", data: (timeseries ?? []).map((p) => p.hour) },
              yAxis: { type: "value" },
              series: [
                {
                  type: "bar",
                  data: (timeseries ?? []).map((p) => p.requests),
                  itemStyle: { color: "#f97316" },
                  barWidth: "60%",
                },
              ],
            }}
          />
        </div>
        <div className="panel-lg">
          <h2 className="text-sm uppercase tracking-wider text-text-dim mb-2">Throughput per Minute</h2>
          <Chart
            option={{
              legend: { data: ["RPM", "TPM"], top: 0 },
              xAxis: { type: "category", data: (timeseries ?? []).map((p) => p.hour) },
              yAxis: { type: "value" },
              series: [
                {
                  name: "RPM",
                  type: "line",
                  smooth: true,
                  data: (timeseries ?? []).map((p) => Number(p.rpm.toFixed(2))),
                  lineStyle: { color: "#22c55e" },
                  itemStyle: { color: "#22c55e" },
                },
                {
                  name: "TPM",
                  type: "line",
                  smooth: true,
                  data: (timeseries ?? []).map((p) => Number(p.tpm.toFixed(0))),
                  lineStyle: { color: "#f59e0b" },
                  itemStyle: { color: "#f59e0b" },
                },
              ],
            }}
          />
        </div>
      </section>
    </div>
  );
}
