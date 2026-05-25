import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";

import { api } from "@/api/client";
import { useJobs, useStatus, useSyncRuns } from "@/hooks/queries";
import { useFilters } from "@/store/filters";
import { formatDateTime, formatInt } from "@/utils/format";

function normalizeLimit(value: number): number {
  return Math.max(1, Math.trunc(value) || 1);
}

function formatJobStatus(value: string): string {
  if (value === "running") return "运行中";
  if (value === "done") return "完成";
  if (value === "failed") return "失败";
  return value;
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
      if (!scope) throw new Error("没有选中网关范围");
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
      if (!scope) throw new Error("没有选中网关范围");
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
          <header className="text-sm font-medium text-text-dim">数据库</header>
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-text-dim">日志总数</dt>
            <dd>{formatInt(status?.total_logs)}</dd>
            <dt className="text-text-dim">最早日志</dt>
            <dd className="font-mono text-xs">{formatDateTime(status?.first_log_at)}</dd>
            <dt className="text-text-dim">最新日志</dt>
            <dd className="font-mono text-xs">{formatDateTime(status?.last_log_at)}</dd>
            <dt className="text-text-dim">已解析</dt>
            <dd>{formatInt(status?.usage_parsed)}</dd>
            <dt className="text-text-dim">无 usage</dt>
            <dd>{formatInt(status?.usage_no_usage)}</dd>
            <dt className="text-text-dim">失败</dt>
            <dd>{formatInt(status?.usage_failed)}</dd>
          </dl>
        </div>

        <div className="panel-lg lg:col-span-2 flex flex-col gap-3">
          <header className="text-sm font-medium text-text-dim">触发同步</header>
          <div className="flex flex-wrap items-end gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-text-dim">数量上限</span>
              <input
                type="number"
                value={limit}
                min={1}
                onChange={(e) => setLimit(normalizeLimit(Number(e.target.value)))}
                className="field w-28"
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={withUsage}
                onChange={(e) => setWithUsage(e.target.checked)}
              />
              <span>同步 usage</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={missingOnly}
                onChange={(e) => setMissingOnly(e.target.checked)}
              />
              <span>仅缺失项</span>
            </label>
            <button
              className="btn-primary"
              onClick={() => triggerSyncLogs.mutate()}
              disabled={!scope || triggerSyncLogs.isPending}
            >
              同步日志
            </button>
            <button
              className="btn"
              onClick={() => triggerSyncUsage.mutate()}
              disabled={!scope || triggerSyncUsage.isPending}
            >
              仅同步 usage
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
        <header className="text-sm font-medium text-text-dim mb-3">任务状态</header>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>任务</th>
                <th>模式</th>
                <th>状态</th>
                <th>目标数</th>
                <th>已解析</th>
                <th>失败</th>
                <th>开始</th>
                <th>结束</th>
                <th>错误</th>
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
                      {formatJobStatus(job.status)}
                    </span>
                  </td>
                  <td>{formatInt(job.targets)}</td>
                  <td>{formatInt(job.usage_parsed)}</td>
                  <td>{formatInt(job.usage_failed)}</td>
                  <td className="font-mono text-xs">{formatDateTime(job.started_at)}</td>
                  <td className="font-mono text-xs">{formatDateTime(job.finished_at)}</td>
                  <td className="text-danger text-xs">{job.error ?? "-"}</td>
                </tr>
              ))}
              {(jobs ?? []).length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-text-dim py-6">
                    暂无进行中或近期任务。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel-lg">
        <header className="text-sm font-medium text-text-dim mb-3">近期同步记录</header>
        <div className="overflow-x-auto">
          <table className="compact">
            <thead>
              <tr>
                <th>记录</th>
                <th>模式</th>
                <th>日志</th>
                <th>已获取</th>
                <th>已解析</th>
                <th>无 usage</th>
                <th>失败</th>
                <th>开始</th>
                <th>结束</th>
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
                  <td className="font-mono text-xs">{formatDateTime(run.started_at)}</td>
                  <td className="font-mono text-xs">{formatDateTime(run.finished_at)}</td>
                </tr>
              ))}
              {(runs ?? []).length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center text-text-dim py-6">
                    暂无同步记录。
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
