# CLAUDE.md

Project-level guidance for AI assistants (Claude, Codex, ...) working in this repository. Pair with `AGENTS.md` for the directory map.

## 项目定位

`cloudflare-ai-gateway-analyzer` 是一个**本地优先的 Cloudflare AI Gateway 日志分析工具**，包含：

- Typer CLI（采集、查询、状态）
- FastAPI 控制面（`/api/v1/*`，OpenAPI 自动产出）
- React + Vite + ECharts 看板（默认暗色、仪表盘式信息密度）
- 单 SQLite 文件存储，`log_events` 是统计事实表，`log_raw` 是 sanitized JSON 辅助表

不是 gateway，不对外暴露代理服务；不引入消息队列、外部数据库或多租户。

## 关键设计约束（别破坏）

- **不持久化请求/响应正文**。`core.sanitizer.sanitize_log_metadata` 是底线，凡涉及 raw JSON 的代码路径都得过它。
- **单一统计事实表**。常规统计围绕 `log_events`；不要恢复 `logs + log_usage + log_metrics + logs_raw` 的 1:1 多表模型。
- **`provider` 就是渠道**。数据库、API、TypeScript 类型仍叫 `provider`；UI 可展示为“渠道”；不要新增 `channel` 字段或 alias。
- **看板/分析层不直接读 Cloudflare**。`analytics/*` 全部经 `cf_aigw_analyzer.data.db.open_readonly_connection`。
- **SQL 下推聚合**。`analytics/` 不允许 `fetch_rows()` 把整张表加载到 Python 内存（v0.2 旧实现的反例）。
- **鉴权一刀切**：`control.auth_token` 非空时，**所有 `/api/v1/*` 路由（包括 GET）** 都走 Bearer 校验。不要为某个路由开口子。
- **默认 loopback**。`control.host=127.0.0.1` 是默认值；改默认要同步更新 `docs/security-and-privacy.md`。
- **数据迁移**：schema v5 对旧 analyzer 表执行 destructive reset，不做旧 SQLite 数据搬迁；用户需要重新 sync。

## 包结构与最近修改的边界

- `cli/` 子命令分文件，主入口 `cli/app.py`。新增子命令同步更新 `tests/integration/test_cli.py` 与 `docs/operations.md`。
- `core/` 是采集 + 解析，写库要走 `data/repository/*`。
- `data/` 的 `schema.py` 与 `migrations.py` 永远耦合：改表结构必须改 `SCHEMA_VERSION` + 增加迁移 handler。
- `analytics/aggregate.py` 构造统一 `GET /api/v1/analytics` payload；前后端契约通过 `control/schemas/analytics.py` 锁定。
- `web/src/api/types.ts` 是手写 TS 类型，**改后端 schema 时同步改这里**。OpenAPI 自动生成（`scripts/generate_openapi.py`）可作为校对工具。

## 测试规范

- pytest + pytest-asyncio + pytest-httpx，所有 HTTP 走 `httpx.MockTransport`。
- 没有 live-network 测试。新增需要真实 Cloudflare 的脚本放 `scripts/` 并标注 `# requires live credentials`。
- 改任何 schema / 路由 / Pydantic 模型都要补单测。
- 跑测试统一用 `PYTHONPATH=src python3 -m pytest -q`，CI 用 `python3 scripts/smoke_local.py` 一键跑全套。

## 常用命令

| 命令                                                           | 用途                                      |
| -------------------------------------------------------------- | ----------------------------------------- |
| `PYTHONPATH=src python3 -m pytest -q`                          | 单元 + 集成测试，离线运行                 |
| `python3 -m ruff check src tests scripts cli.py main.py serve.py` | Lint，零容忍                              |
| `python3 -m ruff format --check src tests scripts cli.py main.py serve.py` | 格式校对                      |
| `python3 cli.py serve`                                        | 启动 FastAPI + 看板（默认 `56000`，或由 `--port` / `control.port` 指定）          |
| `python3 cli.py config show`                                  | 看脱敏后的有效配置                        |
| `python3 scripts/seed_sqlite.py --count 200`                  | 灌入合成数据（不真打 Cloudflare）         |
| `python3 scripts/check_api.py`                                | ASGI 内存调用 GET 路由，确保返回 200      |
| `python3 scripts/generate_openapi.py --output local/openapi.json` | 导出 `local/openapi.json`              |
| `python3 scripts/smoke_local.py`                              | ruff + pytest + openapi + check_api 一站式 |
| `cd web && npm run lint && npm run build`                     | 前端类型检查与生产构建                    |

## 不要做

- 不要在 `legacy/v0.2/` 下做任何修改。那是只读参考。
- 不要在 `analytics/` 里调 Cloudflare。
- 不要给某条路由开 auth 例外。
- 不要把 `raw_json` 还原到统计事实表。
- 不要恢复 `log_usage` / `log_metrics` / `logs_raw` 分裂表作为业务依赖。
- 不要新增 Streamlit / 不要做单独的看板进程。看板就是 `web/` + `control/`。
- 不要假设可以提交 `local/` 或 `config.yaml` 或 `web/dist/`。

## 对外的"未决"事项

- License：用户尚未选择，所有文档不要声明开源协议。
- `.codex/` symlink：当前 repo 内不维护。

## 重构历史

- v0.2 是单包 + Streamlit，源代码保留在 `legacy/v0.2/`。
- v0.3 完全重写，对齐用户其他项目（SouWen / AI-DataFlux / QX-Platform）的范式：
  - 顶层 `cli.py` + `main.py` + `serve.py` 多入口
  - 包内 `cli/`、`core/`、`data/`、`analytics/`、`control/`、`config/`、`models/`、`utils/` 分层
  - FastAPI 后端 + React 前端
  - Docker 三件套
  - hatch + Pydantic v2 + httpx + tenacity + Typer + pytest
- schema v5 在 v0.3 重写基础上进一步简化数据模型：`log_events` 宽表 + `log_raw` 辅助表，统一 analytics endpoint。

具体重构方案见 `local/refactor/plan.md`（gitignored），任务跟踪见 `local/task-tracker.md`，评审报告见 `local/copilot-check.md`。
