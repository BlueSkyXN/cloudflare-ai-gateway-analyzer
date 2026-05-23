# Cloudflare AI Gateway Analyzer

将 Cloudflare AI Gateway 日志采集到本地 SQLite，并通过 FastAPI 控制面 + React 看板进行分析。

- **Runtime**：Python 3.10+，httpx + tenacity + FastAPI + Pydantic v2 + Typer
- **存储**：单 SQLite 文件，scope 由 `(account_id, gateway_id, log_id)` 标识
- **前端**：React 18 + Vite + TypeScript + ECharts + Tailwind（默认暗色，仪表盘式信息密度）
- **部署**：Dockerfile + docker-compose（默认 loopback 绑定 `127.0.0.1:8765`）
- **License**：未选择，源码可读但暂未授予复用许可

## 关键设计

1. **CLI / 后端 / 看板三分离**：`cli.py` 子命令式 CLI，`cf-aigw-analyzer serve` 启动 FastAPI 控制面，前端通过 `/api/v1/*` 调用，单端口托管。
2. **不存请求/响应正文**：`logs.raw_json` 被拆到 `logs_raw` 表并经 `sanitize_log_metadata` 清洗，body 字段递归剔除。
3. **SQL 下推聚合**：dashboard 的 summary / timeseries / model / context bucket 全部在 SQLite 内 group by，避免把整行加载到 Python 内存。
4. **异步并发同步**：`SyncEngine` 用 `asyncio.gather + Semaphore` 跑 `/response` 拉取，回写批量化。
5. **可观测的同步状态**：`sync_runs` 表记录每次运行；前端通过 `/api/v1/sync/jobs/{id}` 与 `/api/v1/sync/runs` 轮询。

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
npm ci          # 首次安装
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
python3 scripts/smoke_local.py
python3 scripts/generate_openapi.py --output local/openapi.json
cd web && npm run lint && npm run build
```

## 项目状态

v0.3 alpha：

- 92 单元 + 集成测试覆盖 data / core / analytics / cli / control
- OpenAPI 17 个路径（含 `/api/v1/sync/jobs/*` 异步任务接口）
- 前端骨架完成，待 `npm ci` + `npm run build` 才可生产托管

`legacy/v0.2/` 保留了上一版完整源码作为参考，不再维护。
