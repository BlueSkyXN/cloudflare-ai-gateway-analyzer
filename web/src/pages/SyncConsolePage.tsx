import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";

import { api } from "@/api/client";
import { useJobs, useStatus, useSyncRuns } from "@/hooks/queries";
import { useFilters } from "@/store/filters";
import { formatInt } from "@/utils/format";

function normalizeLimit(value: number): number {
  return Math.max(1, Math.trunc(value) || 1);
}

export function SyncConsolePage() {
  const scope = useFilters((s) => s.scope);
  const queryClient = useQueryClient();
  const { data: status } = useStatus();
  const { data: jobs } = useJobs();
  const { data: runs } = useSyncRuns(10);

  const [limit, setLimit] = useState<number>(200);
  const [withUsage, setWithUsage] = useState<boolean>(true);
  const [missingOnly, setMissingOnly] = useState<boolean>(true);

  const triggerSyncLogs = useMutation({
    mutationFn: () => {
      if (!scope) throw new Error("没有选中 scope");
      const safeLimit = normalizeLimit(limit);
      return api.triggerSyncLogs({
        account_id: scope.account_id,
        gateway_id: scope.gateway_id,
        limit: safeLimit,
        with_usage: withUsage,
        missing_only: missingOnly,
        usage_limit: withUsage ? safeLimit : undefined,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const triggerSyncUsage = useMutation({
    mutationFn: () => {
      if (!scope) throw new Error("没有选中 scope");
      const safeLimit = normalizeLimit(limit);
      return api.triggerSyncUsage({
        account_id: scope.account_id,
        gateway_id: scope.gateway_id,
        missing_only: missingOnly,
        limit: safeLimit,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="panel-lg flex flex-col gap-3">
          <header className="text-sm uppercase tracking-wider text-text-dim">Database</header>
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-text-dim">Total logs</dt>
            <dd>{formatInt(status?.total_logs)}</dd>
            <dt className="text-text-dim">First log</dt>
            <dd className="font-mono text-xs">{status?.first_log_at ?? "-"}</dd>
            <dt className="text-text-dim">Last log</dt>
            <dd className="font-mono text-xs">{status?.last_log_at ?? "-"}</dd>
            <dt className="text-text-dim">Parsed</dt>
            <dd>{formatInt(status?.usage_parsed)}</dd>
            <dt className="text-text-dim">No usage</dt>
            <dd>{formatInt(status?.usage_no_usage)}</dd>
            <dt className="text-text-dim">Failed</dt>
            <dd>{formatInt(status?.usage_failed)}</dd>
          </dl>
        </div>

        <div className="panel-lg lg:col-span-2 flex flex-col gap-3">
          <header className="text-sm uppercase tracking-wider text-text-dim">Trigger</header>
          <div className="flex flex-wrap items-end gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-text-dim">Limit</span>
              <input
                type="number"
                value={limit}
                min={1}
                onChange={(e) => setLimit(normalizeLimit(Number(e.target.value)))}
                className="bg-bg-subtle border border-line rounded-md px-2 py-1.5 w-28"
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={withUsage}
                onChange={(e) => setWithUsage(e.target.checked)}
              />
              <span>with usage</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={missingOnly}
                onChange={(e) => setMissingOnly(e.target.checked)}
              />
              <span>missing only</span>
            </label>
            <button
              className="btn-primary"
              onClick={() => triggerSyncLogs.mutate()}
              disabled={!scope || triggerSyncLogs.isPending}
            >
              Sync metadata
            </button>
            <button
              className="btn"
              onClick={() => triggerSyncUsage.mutate()}
              disabled={!scope || triggerSyncUsage.isPending}
            >
              Sync usage only
            </button>
          </div>
          {(triggerSyncLogs.error || triggerSyncUsage.error) && (
            <div className="text-danger text-xs">
              {(triggerSyncLogs.error || triggerSyncUsage.error)?.message}
            </div>
          )}
        </div>
      </section>

      <section className="panel-lg">
        <header className="text-sm uppercase tracking-wider text-text-dim mb-3">Jobs (live)</header>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>Job</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Targets</th>
                <th>Parsed</th>
                <th>Failed</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {(jobs ?? []).map((job) => (
                <tr key={job.job_id}>
                  <td className="font-mono text-xs">{job.job_id}</td>
                  <td>{job.mode}</td>
                  <td>
                    <span
                      className={clsx(
                        job.status === "done" && "chip-success",
                        job.status === "running" && "chip",
                        job.status === "failed" && "chip-danger"
                      )}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td>{formatInt(job.targets)}</td>
                  <td>{formatInt(job.usage_parsed)}</td>
                  <td>{formatInt(job.usage_failed)}</td>
                  <td className="font-mono text-xs">{job.started_at?.slice(0, 19)}</td>
                  <td className="font-mono text-xs">{job.finished_at?.slice(0, 19) ?? "-"}</td>
                  <td className="text-danger text-xs">{job.error ?? "-"}</td>
                </tr>
              ))}
              {(jobs ?? []).length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-text-dim py-6">
                    No active or recent jobs.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel-lg">
        <header className="text-sm uppercase tracking-wider text-text-dim mb-3">Recent sync_runs</header>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>Run</th>
                <th>Mode</th>
                <th>Logs</th>
                <th>Fetched</th>
                <th>Parsed</th>
                <th>No usage</th>
                <th>Failed</th>
                <th>Started</th>
                <th>Finished</th>
              </tr>
            </thead>
            <tbody>
              {(runs ?? []).map((run) => (
                <tr key={run.run_id}>
                  <td className="font-mono text-xs">#{run.run_id}</td>
                  <td>{run.mode}</td>
                  <td>{formatInt(run.logs_count)}</td>
                  <td>{formatInt(run.usage_fetched)}</td>
                  <td>{formatInt(run.usage_parsed)}</td>
                  <td>{formatInt(run.usage_no_usage)}</td>
                  <td>{formatInt(run.usage_failed)}</td>
                  <td className="font-mono text-xs">{run.started_at.slice(0, 19)}</td>
                  <td className="font-mono text-xs">{run.finished_at.slice(0, 19)}</td>
                </tr>
              ))}
              {(runs ?? []).length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-text-dim py-6">
                    No sync runs yet.
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
