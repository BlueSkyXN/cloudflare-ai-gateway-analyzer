import { BarChart, LineChart } from "echarts/charts";
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from "echarts/components";
import { connect, init, use, type EChartsCoreOption, type EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import { useUiPreferences, type ThemeMode } from "@/store/ui";

use([
  BarChart,
  LineChart,
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

const palettes = {
  light: {
    text: "#172033",
    dim: "#64748b",
    panel: "#ffffff",
    line: "#d6dee8",
    series: ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"],
  },
  dark: {
    text: "#f1f5f9",
    dim: "#bac6d6",
    panel: "#182130",
    line: "#374359",
    series: ["#60a5fa", "#4ade80", "#fbbf24", "#f87171", "#c084fc"],
  },
};

type Props = {
  option: Record<string, unknown>;
  height?: number;
  group?: string;
};

function styleAxis(axis: unknown, theme: ThemeMode): unknown {
  const palette = palettes[theme];
  const axisDefaults = {
    axisLabel: { color: palette.dim },
    axisLine: { lineStyle: { color: palette.line } },
    splitLine: { lineStyle: { color: palette.line, opacity: theme === "light" ? 0.7 : 0.35 } },
  };

  if (Array.isArray(axis)) {
    return axis.map((item) =>
      item && typeof item === "object" ? { ...axisDefaults, ...item } : item
    );
  }
  if (axis && typeof axis === "object") {
    return { ...axisDefaults, ...axis };
  }
  return axis;
}

function buildOption(option: Record<string, unknown>, theme: ThemeMode): Record<string, unknown> {
  const palette = palettes[theme];
  const baseLegend = { textStyle: { color: palette.dim }, top: 8 };
  const result: Record<string, unknown> = {
    backgroundColor: "transparent",
    color: palette.series,
    textStyle: { color: palette.dim, fontFamily: "inherit" },
    grid: { left: 40, right: 16, top: 40, bottom: 32 },
    legend: baseLegend,
    tooltip: {
      trigger: "axis",
      backgroundColor: palette.panel,
      borderColor: palette.line,
      textStyle: { color: palette.text },
      axisPointer: {
        type: "line",
        lineStyle: { color: palette.dim, opacity: 0.8 },
      },
    },
    ...option,
  };

  if (option.legend && typeof option.legend === "object" && !Array.isArray(option.legend)) {
    result.legend = { ...baseLegend, ...option.legend };
  }
  if (option.xAxis) result.xAxis = styleAxis(option.xAxis, theme);
  if (option.yAxis) result.yAxis = styleAxis(option.yAxis, theme);
  return result;
}

export function Chart({ option, height = 280, group }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const theme = useUiPreferences((s) => s.theme);
  const themedOption = useMemo(() => buildOption(option, theme), [option, theme]);

  useEffect(() => {
    if (!containerRef.current) return undefined;

    const chart = init(containerRef.current, undefined, { renderer: "canvas" });
    const observer = new ResizeObserver(() => chart.resize());
    if (group) chart.group = group;
    if (group) connect(group);
    chartRef.current = chart;
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [group]);

  useEffect(() => {
    chartRef.current?.setOption(themedOption as EChartsCoreOption, {
      notMerge: true,
      lazyUpdate: true,
    });
  }, [themedOption]);

  return (
    <div ref={containerRef} style={{ height, width: "100%" }} aria-label="数据图表" role="img" />
  );
}
