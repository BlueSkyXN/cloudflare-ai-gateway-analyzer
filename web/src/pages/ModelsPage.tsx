import { useMemo } from "react";

import { Chart } from "@/components/Chart";
import { useAnalytics } from "@/hooks/queries";
import { formatDuration, formatFloat, formatInt, formatPercent } from "@/utils/format";

export function ModelsPage() {
  const { data } = useAnalytics();
  const modelRows = data?.by_model ?? [];
  const providerRows = data?.by_provider ?? [];

  const modelOption = useMemo(
    () => ({
      legend: { data: ["请求数", "平均 TPS"], top: 0 },
      xAxis: { type: "category", data: modelRows.slice(0, 12).map((m) => m.model) },
      yAxis: [
        { type: "value", name: "请求数" },
        { type: "value", name: "TPS", position: "right" },
      ],
      series: [
        {
          name: "请求数",
          type: "bar",
          data: modelRows.slice(0, 12).map((m) => m.requests),
        },
        {
          name: "平均 TPS",
          type: "line",
          yAxisIndex: 1,
          data: modelRows.slice(0, 12).map((m) => (m.avg_output_tps ?? 0).toFixed(2)),
        },
      ],
    }),
    [modelRows]
  );

  const providerOption = useMemo(
    () => ({
      legend: { data: ["请求数", "平均总耗时"], top: 0 },
      xAxis: { type: "category", data: providerRows.slice(0, 12).map((p) => p.provider) },
      yAxis: [
        { type: "value", name: "请求数" },
        { type: "value", name: "ms", position: "right" },
      ],
      series: [
        {
          name: "请求数",
          type: "bar",
          data: providerRows.slice(0, 12).map((p) => p.requests),
        },
        {
          name: "平均总耗时",
          type: "line",
          yAxisIndex: 1,
          data: providerRows.slice(0, 12).map((p) => p.avg_total_ms?.toFixed(0) ?? null),
        },
      ],
    }),
    [providerRows]
  );

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="panel-lg">
          <h2 className="text-sm font-medium text-text-dim mb-2">模型请求量 · 平均 TPS</h2>
          <Chart option={modelOption} />
        </div>
        <div className="panel-lg">
          <h2 className="text-sm font-medium text-text-dim mb-2">渠道请求量 · 平均总耗时</h2>
          <Chart option={providerOption} />
        </div>
      </section>

      <section className="panel-lg">
        <h2 className="text-sm font-medium text-text-dim mb-3">模型对比</h2>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>模型</th>
                <th>渠道</th>
                <th>请求数</th>
                <th>成功率</th>
                <th>Tokens</th>
                <th>平均输入</th>
                <th>平均输出</th>
                <th>平均总耗时</th>
                <th>P95</th>
                <th>平均 TPS</th>
              </tr>
            </thead>
            <tbody>
              {modelRows.map((m) => (
                <tr key={m.model}>
                  <td className="font-medium">{m.model}</td>
                  <td className="text-text-dim">{m.providers.join(", ") || "-"}</td>
                  <td>{formatInt(m.requests)}</td>
                  <td>{formatPercent(m.success_rate)}</td>
                  <td>{formatInt(m.total_tokens)}</td>
                  <td>{formatFloat(m.avg_input_tokens, 0)}</td>
                  <td>{formatFloat(m.avg_output_tokens, 0)}</td>
                  <td>{formatDuration(m.avg_total_ms)}</td>
                  <td>{formatDuration(m.p95_total_ms)}</td>
                  <td>{formatFloat(m.avg_output_tps)}</td>
                </tr>
              ))}
              {modelRows.length === 0 && (
                <tr>
                  <td colSpan={10} className="text-center text-text-dim py-6">
                    暂无模型数据。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel-lg">
        <h2 className="text-sm font-medium text-text-dim mb-3">渠道对比</h2>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>渠道</th>
                <th>请求数</th>
                <th>成功率</th>
                <th>Tokens</th>
                <th>平均总耗时</th>
                <th>平均输出时间</th>
                <th>平均 TPS</th>
              </tr>
            </thead>
            <tbody>
              {providerRows.map((p) => (
                <tr key={p.provider}>
                  <td className="font-medium">{p.provider}</td>
                  <td>{formatInt(p.requests)}</td>
                  <td>{formatPercent(p.success_rate)}</td>
                  <td>{formatInt(p.total_tokens)}</td>
                  <td>{formatDuration(p.avg_total_ms)}</td>
                  <td>{formatDuration(p.avg_generation_ms)}</td>
                  <td>{formatFloat(p.avg_output_tps)}</td>
                </tr>
              ))}
              {providerRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-text-dim py-6">
                    暂无渠道数据。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
