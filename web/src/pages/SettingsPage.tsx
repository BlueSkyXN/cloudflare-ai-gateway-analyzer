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
        <header className="text-sm font-medium text-text-dim">当前网关范围</header>
        {scope ? (
          <dl className="grid grid-cols-2 gap-y-1 text-sm">
            <dt className="text-text-dim">Account</dt>
            <dd className="font-mono">{scope.account_id}</dd>
            <dt className="text-text-dim">Gateway</dt>
            <dd className="font-mono">{scope.gateway_id}</dd>
            <dt className="text-text-dim">日志数</dt>
            <dd>{scope.logs.toLocaleString("zh-CN")}</dd>
          </dl>
        ) : (
          <span className="text-text-dim text-sm">尚未选择网关范围。</span>
        )}
      </section>

      <section className="panel-lg flex flex-col gap-3">
        <header className="text-sm font-medium text-text-dim">Bearer token</header>
        <p className="text-xs text-text-dim">
          如果 control plane 配置了 <code>control.auth_token</code>，在这里填入同一个值。
          它会保存在 <code>localStorage</code>，并作为 <code>Authorization: Bearer ...</code>
          发送到每个 API 请求。
        </p>
        <div className="flex items-center gap-2">
          <input
            type="password"
            className="field flex-1 font-mono"
            value={token}
            placeholder="本机无鉴权模式可以留空"
            onChange={(e) => setToken(e.target.value)}
          />
          <button className="btn-primary" onClick={persistToken}>
            保存
          </button>
        </div>
        {tokenSaved && <span className="text-xs text-success">已保存。</span>}
      </section>

      <section className="panel-lg flex flex-col gap-3">
        <header className="text-sm font-medium text-text-dim">当前筛选</header>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="flex flex-col gap-1">
            <span className="text-text-dim">模型</span>
            <span className="font-medium">{model ?? "全部模型"}</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-text-dim">渠道</span>
            <span className="font-medium">{provider ?? "全部渠道"}</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-text-dim">结果</span>
            <span className="font-medium">
              {successFilter === "success" ? "成功" : successFilter === "failed" ? "失败" : "全部"}
            </span>
          </div>
        </div>
      </section>

      <section className="panel-lg">
        <header className="text-sm font-medium text-text-dim mb-3">当前配置（已脱敏）</header>
        {config ? (
          <pre className="text-xs bg-bg overflow-x-auto p-3 rounded border border-line">
{JSON.stringify(config, null, 2)}
          </pre>
        ) : (
          <span className="text-text-dim text-sm">加载中...</span>
        )}
      </section>

      {config && (
        <section className="panel-lg text-sm text-text-dim">
          <header className="font-medium mb-2">存储</header>
          <p>
            <span className="text-text">{config.storage.data_dir}/{config.storage.db_filename}</span>
            {" · "}
            文件大小可通过 <code className="text-text">cf-aigw-analyzer status</code> 查看 →
            {" "}
            <span className="font-mono">{formatBytes(undefined)}</span>
          </p>
        </section>
      )}
    </div>
  );
}
