import { useMemo } from "react";

import { Chart } from "@/components/Chart";
import { KpiCard } from "@/components/KpiCard";
import { useAnalytics } from "@/hooks/queries";
import { formatDuration, formatFloat, formatInt, formatPercent } from "@/utils/format";

export function OverviewPage() {
  const { data } = useAnalytics();
  const summary = data?.summary;
  const points = data?.timeseries ?? [];

  const requestOption = useMemo(
    () => ({
      xAxis: { type: "category", data: points.map((p) => p.hour) },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          data: points.map((p) => p.requests),
          barWidth: "60%",
        },
      ],
    }),
    [points]
  );

  const throughputOption = useMemo(
    () => ({
      legend: { data: ["RPM", "TPM"], top: 0 },
      xAxis: { type: "category", data: points.map((p) => p.hour) },
      yAxis: { type: "value" },
      series: [
        {
          name: "RPM",
          type: "line",
          smooth: true,
          data: points.map((p) => Number(p.rpm.toFixed(2))),
        },
        {
          name: "TPM",
          type: "line",
          smooth: true,
          data: points.map((p) => Number(p.tpm.toFixed(0))),
        },
      ],
    }),
    [points]
  );

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <KpiCard label="请求数" value={formatInt(summary?.requests)} />
        <KpiCard
          label="成功率"
          value={formatPercent(summary?.success_rate)}
          hint={`${formatInt(summary?.success_count)} 成功`}
        />
        <KpiCard label="总 Tokens" value={formatInt(summary?.total_tokens)} />
        <KpiCard label="平均总耗时" value={formatDuration(summary?.avg_total_ms)} />
        <KpiCard label="平均输入 TPS" value={formatFloat(summary?.avg_input_tps)} />
        <KpiCard label="平均输出 TPS" value={formatFloat(summary?.avg_output_tps)} />
        <KpiCard label="输入 Tokens" value={formatInt(summary?.input_tokens)} />
        <KpiCard label="输出 Tokens" value={formatInt(summary?.output_tokens)} />
        <KpiCard label="推理 Tokens" value={formatInt(summary?.reasoning_tokens)} />
        <KpiCard label="P95 总耗时" value={formatDuration(summary?.p95_total_ms)} />
        <KpiCard label="平均输出时间" value={formatDuration(summary?.avg_generation_ms)} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="panel-lg">
          <h2 className="text-sm font-medium text-text-dim mb-2">小时请求量</h2>
          <Chart option={requestOption} />
        </div>
        <div className="panel-lg">
          <h2 className="text-sm font-medium text-text-dim mb-2">每分钟吞吐</h2>
          <Chart option={throughputOption} />
        </div>
      </section>
    </div>
  );
}
