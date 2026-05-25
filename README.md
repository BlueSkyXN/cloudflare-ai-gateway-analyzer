# Cloudflare AI Gateway Analyzer

将 Cloudflare AI Gateway 日志采集到本地 SQLite，并通过 FastAPI 控制面 + React 看板进行分析。

- **Runtime**：Python 3.10+，httpx + tenacity + FastAPI + Pydantic v2 + Typer
- **存储**：单 SQLite 文件，`log_events` 是统计事实表，`log_raw` 只保存 sanitized JSON
- **前端**：React 18 + Vite + TypeScript + ECharts + Tailwind（默认暗色，仪表盘式信息密度）
- **部署**：Dockerfile + docker-compose（默认 loopback 绑定 `127.0.0.1:8765`）
- **License**：未选择，源码可读但暂未授予复用许可

## 关键设计

1. **CLI / 后端 / 看板三分离**：`cli.py` 子命令式 CLI，`cf-aigw-analyzer serve` 启动 FastAPI 控制面，前端通过 `/api/v1/*` 调用，单端口托管。
2. **单一日志事实表**：常用统计字段直接落到 `log_events`，metadata sync 插入同一行，usage sync 回填同一行，避免 `logs + log_usage + log_metrics` 的 1:1 多表 join。
3. **不存请求/响应正文**：`log_raw.raw_json` 只保存经 `sanitize_log_metadata` 清洗后的 Cloudflare log JSON；`/response` 只用于解析 usage，响应正文不落盘。
4. **统一 analytics API**：`GET /api/v1/analytics` 一次返回 `summary`、`timeseries`、`by_provider`、`by_model`、`events` 和 `filter_options`，前端各页面共享同一份数据。
5. **`provider` 就是渠道**：筛选和分组字段统一为 `provider`，不新增 `channel` 字段或 API alias。
6. **SQL 下推聚合**：请求数、tokens、耗时、TPS、分位数和按渠道/模型拆分都在 SQLite 内聚合，避免把整表加载到 Python 内存。
7. **可观测且可重跑的同步状态**：`sync_runs` 记录每次运行，`sync_state` 支持显式增量同步，`sync_locks` 防止同一 scope 被多个 agent 同时写入。

## 快速开始

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 配置

复制公开模板并填入：

```bash
cp config-example.yaml config.yaml
# 编辑 config.yaml，或者用环境变量覆盖
export CF_API_TOKEN="your-token"
```

环境变量优先级最高，详见 [docs/config.md](docs/config.md)。

### CLI 操作

```bash
# 初始化 SQLite
python cli.py init

# 同步元数据 + usage
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --with-usage --missing-only

# 后续给 AI/cron 重复执行时，用带重叠窗口的增量同步
python cli.py sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --incremental --with-usage --missing-only

# 启动控制面 + 看板
python cli.py serve         # http://127.0.0.1:8765

# 本地查询
python cli.py query -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --format table --limit 50

# 状态摘要
python cli.py status
```

完整命令见 `python cli.py --help`。

### 前端开发

```bash
cd web
npm install     # 首次安装；生成 lockfile 后可改用 npm ci
npm run dev     # http://127.0.0.1:5173，自动代理 /api → 8765
npm run build   # 产出 web/dist/，由 FastAPI 静态托管
```

### Docker

```bash
docker compose up -d           # loopback bind 127.0.0.1:8765
docker compose exec cf-aigw \
  python cli.py sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --with-usage
```

## 文档

- [Architecture](docs/architecture.md)：模块分层、数据流
- [API contract](docs/api-contract.md)：REST 路由清单、鉴权
- [Data model](docs/data-model.md)：表结构、索引、迁移
- [Config](docs/config.md)：YAML schema、env 优先级
- [Operations](docs/operations.md)：同步、查询、看板、Docker
- [Security & privacy](docs/security-and-privacy.md)：脱敏、loopback 边界
- [Development](docs/development.md)：测试、构建、贡献

## 验证

```bash
PYTHONPATH=src python3 -m pytest -q
python3 -m ruff check src tests scripts cli.py main.py serve.py
python3 -m ruff format --check src tests scripts cli.py main.py serve.py
python3 scripts/smoke_local.py
python3 scripts/generate_openapi.py --output local/openapi.json
python3 scripts/check_api.py
cd web && npm run lint && npm run build
```

## 项目状态

当前主线：

- SQLite schema v5：`log_events` 宽表 + `log_raw` 辅助表；旧 SQLite 数据不迁移，升级时 destructive reset 后重新 sync。
- OpenAPI 12 个路径，analytics 主入口为 `GET /api/v1/analytics`。
- 89 个单元 + 集成测试覆盖 data / core / analytics / cli / control。
- 前端保留总览、模型、延迟、事件、同步、设置多页；analytics 页面共用统一接口。

`legacy/v0.2/` 保留了上一版完整源码作为参考，不再维护。
