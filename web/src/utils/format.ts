const intFormatter = new Intl.NumberFormat("zh-CN");
const floatFormatters = new Map<number, Intl.NumberFormat>();
const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return intFormatter.format(value);
}

export function formatFloat(value: number | null | undefined, digits = 2, suffix = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  let formatter = floatFormatters.get(digits);
  if (!formatter) {
    formatter = new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    floatFormatters.set(digits, formatter);
  }
  return `${formatter.format(value)}${suffix}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDuration(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  if (value < 1000) return `${value.toFixed(0)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatBytes(value: number | null | undefined): string {
  if (!value) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let v = value;
  let idx = 0;
  while (v >= 1024 && idx < units.length - 1) {
    v /= 1024;
    idx += 1;
  }
  return `${v.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 19);
  return dateTimeFormatter.format(parsed);
}

export function shortenId(value: string | null | undefined, head = 6, tail = 4): string {
  if (!value) return "-";
  if (value.length <= head + tail + 3) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}
