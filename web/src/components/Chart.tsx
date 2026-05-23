import ReactECharts from "echarts-for-react";

const baseOption = {
  backgroundColor: "transparent",
  textStyle: { color: "#9aa4b8", fontFamily: "inherit" },
  grid: { left: 40, right: 16, top: 40, bottom: 32 },
  legend: { textStyle: { color: "#9aa4b8" }, top: 8 },
  tooltip: { trigger: "axis", backgroundColor: "#111826", borderColor: "#202737", textStyle: { color: "#e5ecf4" } },
};

type Props = {
  option: Record<string, unknown>;
  height?: number;
};

export function Chart({ option, height = 280 }: Props) {
  return (
    <ReactECharts
      option={{ ...baseOption, ...option }}
      style={{ height, width: "100%" }}
      notMerge
      lazyUpdate
      theme="dark"
    />
  );
}
