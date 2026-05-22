"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .cloudflare import DEFAULT_BASE_URL, CloudflareApiError, CloudflareClient
from .database import AnalyzerDatabase
from .filters import DIRECTION_CHOICES, MAX_PER_PAGE, ORDER_BY_CHOICES, LogFilters
from .output import emit_rows, print_table
from .paths import resolve_db_path
from .sync import sync_gateways, sync_logs, sync_usage


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected one of: true/false/1/0/yes/no")


def add_storage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", help="SQLite 文件路径；默认 local/data/cloudflare_ai_gateway.sqlite")
    parser.add_argument("--data-dir", help="默认 SQLite 目录；默认项目内 local/data")


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-token", help="Cloudflare API Token；默认读取 CF_API_TOKEN")
    parser.add_argument("--email", help="Cloudflare email；默认读取 CF_EMAIL")
    parser.add_argument("--api-key", help="Cloudflare Global API Key；默认读取 CF_API_KEY")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=30.0, help=argparse.SUPPRESS)
    parser.add_argument("--retries", type=int, default=3, help=argparse.SUPPRESS)


def add_account_arg(parser: argparse.ArgumentParser, required: bool = True) -> None:
    parser.add_argument("--account-id", "-a", required=required, help="Cloudflare Account ID")


def add_gateway_arg(parser: argparse.ArgumentParser, required: bool = True) -> None:
    parser.add_argument("--gateway-id", "-g", required=required, help="Cloudflare AI Gateway ID")


def add_gateway_selector_args(parser: argparse.ArgumentParser, required: bool = True) -> None:
    parser.add_argument("--gateway-id", "-g", required=False, help="Cloudflare AI Gateway ID")
    parser.add_argument("--gateway-name", help="Cloudflare AI Gateway 名称，例如 open")
    if required:
        parser.set_defaults(_gateway_required=True)


def add_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=int, default=1, help="起始页")
    parser.add_argument("--per-page", type=int, default=MAX_PER_PAGE, help="每页数量，Cloudflare 最大 50")
    parser.add_argument("--order-by", choices=ORDER_BY_CHOICES)
    parser.add_argument("--direction", choices=DIRECTION_CHOICES)
    parser.add_argument("--start-date", help="开始时间，例如 2026-05-01 或 2026-05-01T00:00:00Z")
    parser.add_argument("--end-date", help="结束时间")
    parser.add_argument("--model", help="按模型过滤")
    parser.add_argument("--provider", help="按 provider 过滤")
    parser.add_argument("--model-type", help="按模型类型过滤")
    parser.add_argument("--search", help="Cloudflare 日志搜索关键词")
    parser.add_argument("--cached", type=parse_bool, help="true/false")
    parser.add_argument("--success", type=parse_bool, help="true/false")
    parser.add_argument("--feedback", type=int, choices=(0, 1))
    parser.add_argument("--min-cost", type=float)
    parser.add_argument("--max-cost", type=float)
    parser.add_argument("--min-duration", type=float)
    parser.add_argument("--max-duration", type=float)
    parser.add_argument("--min-tokens-in", type=int)
    parser.add_argument("--max-tokens-in", type=int)
    parser.add_argument("--min-tokens-out", type=int)
    parser.add_argument("--max-tokens-out", type=int)
    parser.add_argument("--min-total-tokens", type=int)
    parser.add_argument("--max-total-tokens", type=int)
    parser.add_argument("--meta-info", action="store_true", help="请求 Cloudflare 返回 meta_info")


def build_client(args: argparse.Namespace) -> CloudflareClient:
    return CloudflareClient(
        api_token=args.api_token,
        email=args.email,
        api_key=args.api_key,
        base_url=args.base_url,
        timeout=args.timeout,
        retries=args.retries,
    )


def db_path_for(args: argparse.Namespace) -> Path:
    return resolve_db_path(args.db, args.data_dir, getattr(args, "gateway_id", None))


def resolve_gateway_for_api(args: argparse.Namespace, client: CloudflareClient) -> str:
    if getattr(args, "gateway_id", None):
        return args.gateway_id
    if getattr(args, "gateway_name", None):
        gateway_id = client.resolve_gateway_id(args.account_id, args.gateway_name)
        if gateway_id:
            print(f"已解析 gateway: {args.gateway_name} -> {gateway_id}")
            return gateway_id
        raise ValueError(f"没有在 account {args.account_id} 下找到 gateway: {args.gateway_name}")
    if getattr(args, "_gateway_required", False):
        raise ValueError("需要提供 --gateway-id 或 --gateway-name")
    return ""


def resolve_gateway_for_db(args: argparse.Namespace, db: AnalyzerDatabase) -> str | None:
    if getattr(args, "gateway_id", None):
        return args.gateway_id
    if getattr(args, "gateway_name", None):
        if not getattr(args, "account_id", None):
            raise ValueError("按 gateway name 查询本地库时需要提供 --account-id")
        gateway_id = db.resolve_gateway_id(args.account_id, args.gateway_name)
        if gateway_id:
            return gateway_id
        raise ValueError(f"本地 SQLite 中没有找到 gateway: {args.gateway_name}")
    if getattr(args, "_gateway_required", False):
        raise ValueError("需要提供 --gateway-id 或 --gateway-name")
    return None


def cmd_init(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    with AnalyzerDatabase(db_path):
        pass
    print(f"SQLite 已初始化: {db_path}")
    return 0


def cmd_accounts(args: argparse.Namespace) -> int:
    client = build_client(args)
    accounts = list(client.iter_accounts())
    rows = [
        {
            "account_id": account.get("id"),
            "name": account.get("name"),
            "type": account.get("type"),
            "created_on": account.get("created_on"),
        }
        for account in accounts
    ]
    print_table(rows, ("account_id", "name", "type", "created_on"))
    return 0


def cmd_gateways(args: argparse.Namespace) -> int:
    client = build_client(args)
    account_ids = [args.account_id] if args.account_id else [str(account.get("id")) for account in client.iter_accounts()]
    rows = []
    saved = 0
    db_path = db_path_for(args)
    db = AnalyzerDatabase(db_path) if args.save else None
    try:
        for account_id in account_ids:
            gateways = list(client.iter_gateways(account_id))
            if db is not None:
                saved += db.upsert_gateways(account_id, gateways)
            for gateway in gateways:
                rows.append(
                    {
                        "account_id": account_id,
                        "gateway_id": gateway.get("id"),
                        "name": gateway.get("name"),
                        "created_at": gateway.get("created_at"),
                        "collect_logs": gateway.get("collect_logs"),
                    }
                )
    finally:
        if db is not None:
            db.close()

    print_table(rows, ("account_id", "gateway_id", "name", "created_at", "collect_logs"))
    if args.save:
        print(f"已写入 SQLite: {saved} 个 gateway -> {db_path}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    filters = LogFilters.from_args(args)
    client = build_client(args)
    gateway_id = resolve_gateway_for_api(args, client)
    with AnalyzerDatabase(db_path) as db:
        count = sync_logs(db, client, args.account_id, gateway_id, filters, limit=args.limit)
        print(f"\nmetadata 同步完成: {count} 条 -> {db_path}")
        if args.with_usage:
            stats = sync_usage(
                db,
                client,
                args.account_id,
                gateway_id,
                missing_only=args.missing_only,
                refresh=args.refresh_usage,
                retry_failed=not args.no_retry_failed,
                workers=args.usage_workers,
                limit=args.usage_limit,
            )
            print(
                "\nusage 同步完成: "
                f"targets={stats.targets}, fetched={stats.fetched}, "
                f"parsed={stats.parsed}, no_usage={stats.no_usage}, failed={stats.failed}"
            )
    return 0


def cmd_sync_usage(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    client = build_client(args)
    gateway_id = resolve_gateway_for_api(args, client)
    with AnalyzerDatabase(db_path) as db:
        stats = sync_usage(
            db,
            client,
            args.account_id,
            gateway_id,
            missing_only=args.missing_only,
            refresh=args.refresh,
            retry_failed=not args.no_retry_failed,
            workers=args.usage_workers,
            limit=args.limit,
        )
    print(
        f"usage 同步完成: targets={stats.targets}, fetched={stats.fetched}, "
        f"parsed={stats.parsed}, no_usage={stats.no_usage}, failed={stats.failed} -> {db_path}"
    )
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    with AnalyzerDatabase(db_path) as db:
        gateway_id = resolve_gateway_for_db(args, db)
        rows = db.query_logs(
            args.account_id,
            gateway_id,
            start_date=args.start_date,
            end_date=args.end_date,
            provider=args.provider,
            model=args.model,
            model_type=args.model_type,
            success=args.success,
            cached=args.cached,
            search=args.search,
            limit=args.limit,
        )
    emit_rows(
        rows,
        args.format,
        args.output,
        include_raw_json=args.include_raw_json,
        include_scope=args.include_scope,
    )
    if args.output:
        print(f"已输出 {len(rows)} 条 -> {args.output}")
    else:
        print(f"本次返回 {len(rows)} 条")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    with AnalyzerDatabase(db_path) as db:
        gateway_id = resolve_gateway_for_db(args, db)
        summary = db.summary(args.account_id, gateway_id)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_vacuum(args: argparse.Namespace) -> int:
    db_path = db_path_for(args)
    with AnalyzerDatabase(db_path) as db:
        db.vacuum()
    print(f"SQLite VACUUM 完成: {db_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cf-aigw-analyzer",
        description="Cloudflare AI Gateway SQLite 采集与分析工具（单 SQLite，无 XLSX）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="初始化 SQLite")
    add_storage_args(init)
    init.set_defaults(func=cmd_init)

    accounts = subparsers.add_parser("accounts", help="列出 Cloudflare accounts")
    add_auth_args(accounts)
    accounts.set_defaults(func=cmd_accounts)

    gateways = subparsers.add_parser("gateways", help="列出账户下 AI Gateway")
    add_auth_args(gateways)
    add_storage_args(gateways)
    add_account_arg(gateways, required=False)
    gateways.add_argument("--save", action="store_true", help="同时写入 SQLite gateways 表")
    gateways.set_defaults(func=cmd_gateways)

    sync = subparsers.add_parser("sync", help="同步日志 metadata 到 SQLite")
    add_auth_args(sync)
    add_storage_args(sync)
    add_account_arg(sync)
    add_gateway_selector_args(sync)
    add_filter_args(sync)
    sync.add_argument("--limit", type=int, help="最多同步多少条日志")
    sync.add_argument("--with-usage", action="store_true", help="同步 metadata 后继续解析 response usage")
    sync.add_argument("--missing-only", action="store_true", help="usage 只处理缺 token 或未解析的日志")
    sync.add_argument("--refresh-usage", action="store_true", help="忽略已有 usage 记录并重新抓取")
    sync.add_argument("--no-retry-failed", action="store_true", help="不重试已有 failed 状态的 usage")
    sync.add_argument("--usage-workers", type=int, default=8, help="usage 并发数")
    sync.add_argument("--usage-limit", type=int, help="最多同步多少条 usage")
    sync.set_defaults(func=cmd_sync)

    usage = subparsers.add_parser("sync-usage", help="只同步 response usage")
    add_auth_args(usage)
    add_storage_args(usage)
    add_account_arg(usage)
    add_gateway_selector_args(usage)
    usage.add_argument("--missing-only", action="store_true", help="只处理缺 token 或未解析的日志")
    usage.add_argument("--refresh", action="store_true", help="忽略已有 usage 记录并重新抓取")
    usage.add_argument("--no-retry-failed", action="store_true", help="不重试已有 failed 状态的 usage")
    usage.add_argument("--usage-workers", type=int, default=8, help="并发数")
    usage.add_argument("--limit", type=int, help="最多同步多少条")
    usage.set_defaults(func=cmd_sync_usage)

    query = subparsers.add_parser("query", help="查询本地 SQLite")
    add_storage_args(query)
    add_account_arg(query)
    add_gateway_selector_args(query)
    query.add_argument("--start-date")
    query.add_argument("--end-date")
    query.add_argument("--provider")
    query.add_argument("--model")
    query.add_argument("--model-type")
    query.add_argument("--success", type=parse_bool)
    query.add_argument("--cached", type=parse_bool)
    query.add_argument("--search")
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--format", choices=("table", "json", "csv"), default="table")
    query.add_argument("--output")
    query.add_argument("--include-raw-json", action="store_true", help="输出 sanitized raw_json（默认排除）")
    query.add_argument("--include-scope", action="store_true", help="输出 account_id/gateway_id（默认排除）")
    query.set_defaults(func=cmd_query)

    status = subparsers.add_parser("status", help="查看 SQLite 状态")
    add_storage_args(status)
    add_account_arg(status, required=False)
    add_gateway_selector_args(status, required=False)
    status.set_defaults(func=cmd_status)

    vacuum = subparsers.add_parser("vacuum", help="执行 SQLite VACUUM")
    add_storage_args(vacuum)
    add_gateway_arg(vacuum, required=False)
    vacuum.set_defaults(func=cmd_vacuum)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CloudflareApiError as exc:
        print(f"Cloudflare API 错误: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
