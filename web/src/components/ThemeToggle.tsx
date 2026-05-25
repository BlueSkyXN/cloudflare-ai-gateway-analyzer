import clsx from "clsx";

import { useUiPreferences, type ThemeMode } from "@/store/ui";

const themes: Array<{ value: ThemeMode; label: string }> = [
  { value: "light", label: "浅色" },
  { value: "dark", label: "深色" },
];

export function ThemeToggle() {
  const theme = useUiPreferences((s) => s.theme);
  const setTheme = useUiPreferences((s) => s.setTheme);

  return (
    <div className="flex shrink-0 rounded-md border border-line bg-bg-subtle p-0.5" role="group" aria-label="主题">
      {themes.map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => setTheme(item.value)}
          className={clsx(
            "px-2.5 py-1 text-sm rounded transition-colors",
            theme === item.value ? "bg-bg-panel text-text shadow-sm" : "text-text-dim hover:text-text"
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
