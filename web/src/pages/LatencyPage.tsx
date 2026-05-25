import { useMemo } from "react";

import { Chart } from "@/components/Chart";
import { KpiCard } from "@/components/KpiCard";
import { useAnalytics } from "@/hooks/queries";
import { formatDuration, formatFloat } from "@/utils/format";

export function LatencyPage() {
  const { data } = useAnalytics();
  const summary = data?.summary;
  const points = data?.timeseries ?? [];

  const latencyOption = useMemo(
    () => ({
      legend: { data: ["总耗时", "首段延迟", "输出时间"], top: 0 },
      xAxis: { type: "category", data: points.map((p) => p.hour) },
      yAxis: { type: "value", name: "ms" },
      series: [
        {
          name: "总耗时",
          type: "line",
          smooth: true,
          data: points.map((p) => p.avg_total_ms?.toFixed(0) ?? null),
        },
        {
          name: "首段延迟",
          type: "line",
          smooth: true,
          data: points.map((p) => p.avg_latency_ms?.toFixed(0) ?? null),
        },
        {
          name: "输出时间",
          type: "line",
          smooth: true,
          data: points.map((p) => p.avg_generation_ms?.toFixed(0) ?? null),
        },
      ],
    }),
    [points]
  );

  const tpsOption = useMemo(
    () => ({
      legend: { data: ["平均 TPS", "可见 TPS"], top: 0 },
      xAxis: { type: "category", data: points.map((p) => p.hour) },
      yAxis: { type: "value" },
      series: [
        {
          name: "平均 TPS",
          type: "line",
          smooth: true,
          data: points.map((p) => p.avg_output_tps?.toFixed(2) ?? null),
        },
        {
          name: "可见 TPS",
          type: "line",
          smooth: true,
          data: points.map((p) => p.avg_visible_output_tps?.toFixed(2) ?? null),
        },
      ],
    }),
    [points]
  );

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label="平均总耗时" value={formatDuration(summary?.avg_total_ms)} />
        <KpiCard label="平均首段延迟" value={formatDuration(summary?.avg_latency_ms)} />
        <KpiCard label="平均输出时间" value={formatDuration(summary?.avg_generation_ms)} />
        <KpiCard label="P95 总耗时" value={formatDuration(summary?.p95_total_ms)} />
        <KpiCard label="平均 TPS" value={formatFloat(summary?.avg_output_tps)} />
      </section>

      <section className="panel-lg">
        <h2 className="text-sm font-medium text-text-dim mb-2">按小时耗时</h2>
        <Chart option={latencyOption} />
      </section>

      <section className="panel-lg">
        <h2 className="text-sm font-medium text-text-dim mb-2">按小时输出 TPS</h2>
        <Chart option={tpsOption} />
      </section>
    </div>
  );
}
