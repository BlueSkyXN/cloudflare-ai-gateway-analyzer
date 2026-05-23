import { useEffect, useState } from "react";

import { useConfig } from "@/hooks/queries";
import { useFilters } from "@/store/filters";
import { formatBytes } from "@/utils/format";

const TOKEN_STORAGE_KEY = "cf-aigw-token";

export function SettingsPage() {
  const { data: config } = useConfig();
  const scope = useFilters((s) => s.scope);
  const model = useFilters((s) => s.model);
  const provider = useFilters((s) => s.provider);
  const successFilter = useFilters((s) => s.successFilter);
  const setModel = useFilters((s) => s.setModel);
  const setProvider = useFilters((s) => s.setProvider);
  const setSuccessFilter = useFilters((s) => s.setSuccessFilter);

  const [token, setToken] = useState<string>("");
  const [tokenSaved, setTokenSaved] = useState<boolean>(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (stored) setToken(stored);
  }, []);

  const persistToken = () => {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    setTokenSaved(true);
    window.setTimeout(() => setTokenSaved(false), 1500);
  };

  return (
    <div className="flex flex-col gap-6">
      <section className="panel-lg flex flex-col gap-3">
        <header className="text-sm uppercase tracking-wider text-text-dim">Active scope</header>
        {scope ? (
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-text-dim">Account</dt>
            <dd className="font-mono">{scope.account_id}</dd>
            <dt className="text-text-dim">Gateway</dt>
            <dd className="font-mono">{scope.gateway_id}</dd>
            <dt className="text-text-dim">Logs</dt>
            <dd>{scope.logs.toLocaleString()}</dd>
          </dl>
        ) : (
          <span className="text-text-dim text-sm">No scope selected.</span>
        )}
      </section>

      <section className="panel-lg flex flex-col gap-3">
        <header className="text-sm uppercase tracking-wider text-text-dim">Bearer token</header>
        <p className="text-xs text-text-dim">
          If the control plane is configured with <code>control.auth_token</code>, set the matching value
          here. Stored in <code>localStorage</code> and sent as <code>Authorization: Bearer …</code> on
          every API call.
        </p>
        <div className="flex items-center gap-2">
          <input
            type="password"
            className="bg-bg-subtle border border-line rounded-md px-2 py-1.5 flex-1 font-mono text-sm"
            value={token}
            placeholder="(leave empty for loopback mode)"
            onChange={(e) => setToken(e.target.value)}
          />
          <button className="btn-primary" onClick={persistToken}>
            Save
          </button>
        </div>
        {tokenSaved && <span className="text-xs text-success">Saved.</span>}
      </section>

      <section className="panel-lg flex flex-col gap-3">
        <header className="text-sm uppercase tracking-wider text-text-dim">Local filters</header>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-text-dim">Model</span>
            <input
              className="bg-bg-subtle border border-line rounded-md px-2 py-1.5"
              value={model ?? ""}
              onChange={(e) => setModel(e.target.value || null)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-dim">Provider</span>
            <input
              className="bg-bg-subtle border border-line rounded-md px-2 py-1.5"
              value={provider ?? ""}
              onChange={(e) => setProvider(e.target.value || null)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-text-dim">Result</span>
            <select
              className="bg-bg-subtle border border-line rounded-md px-2 py-1.5"
              value={successFilter}
              onChange={(e) =>
                setSuccessFilter(e.target.value as "all" | "success" | "failed")
              }
            >
              <option value="all">All</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
            </select>
          </label>
        </div>
      </section>

      <section className="panel-lg">
        <header className="text-sm uppercase tracking-wider text-text-dim mb-3">Effective config (redacted)</header>
        {config ? (
          <pre className="text-xs bg-bg overflow-x-auto p-3 rounded border border-line">
{JSON.stringify(config, null, 2)}
          </pre>
        ) : (
          <span className="text-text-dim text-sm">Loading…</span>
        )}
      </section>

      {config && (
        <section className="panel-lg text-sm text-text-dim">
          <header className="uppercase tracking-wider mb-2">Storage</header>
          <p>
            <span className="text-text">{config.storage.data_dir}/{config.storage.db_filename}</span>
            {" · "}
            on-disk size shown via <code className="text-text">cf-aigw-analyzer status</code> →
            {" "}
            <span className="font-mono">{formatBytes(undefined)}</span> (run status command).
          </p>
        </section>
      )}
    </div>
  );
}
