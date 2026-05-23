import { useEffect } from "react";

import { useScopes } from "@/hooks/queries";
import { useFilters } from "@/store/filters";
import { shortenId } from "@/utils/format";

const TIME_RANGES = [
  { value: "all", label: "All" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
] as const;

export function ScopeSelector() {
  const { data: scopes, isLoading } = useScopes();
  const scope = useFilters((s) => s.scope);
  const setScope = useFilters((s) => s.setScope);
  const timeRange = useFilters((s) => s.timeRange);
  const setTimeRange = useFilters((s) => s.setTimeRange);

  useEffect(() => {
    if (!scope && scopes && scopes.length > 0) {
      setScope(scopes[0]);
    }
  }, [scope, scopes, setScope]);

  return (
    <div className="flex items-center gap-2">
      <select
        className="bg-bg-subtle border border-line rounded-md px-2 py-1.5 text-sm min-w-[260px]"
        value={scope ? `${scope.account_id}/${scope.gateway_id}` : ""}
        disabled={isLoading || !scopes || scopes.length === 0}
        onChange={(e) => {
          const target = scopes?.find(
            (s) => `${s.account_id}/${s.gateway_id}` === e.target.value
          );
          if (target) setScope(target);
        }}
      >
        {!scopes || scopes.length === 0 ? (
          <option value="">(no data)</option>
        ) : (
          scopes.map((s) => (
            <option key={`${s.account_id}/${s.gateway_id}`} value={`${s.account_id}/${s.gateway_id}`}>
              {s.name} · {shortenId(s.account_id)} · {s.logs.toLocaleString()} logs
            </option>
          ))
        )}
      </select>
      <div className="flex bg-bg-subtle border border-line rounded-md">
        {TIME_RANGES.map((range) => (
          <button
            key={range.value}
            onClick={() => setTimeRange(range.value)}
            className={`px-2.5 py-1.5 text-sm ${
              timeRange === range.value ? "bg-bg-panel text-text" : "text-text-dim hover:text-text"
            }`}
          >
            {range.label}
          </button>
        ))}
      </div>
    </div>
  );
}
