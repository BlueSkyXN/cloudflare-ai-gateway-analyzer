"""`cf-aigw-analyzer serve` — boot the FastAPI control plane.

Lives behind a lazy import so that importing the CLI does not pull in
FastAPI/uvicorn for the no-server commands.
"""

from __future__ import annotations

import typer

from cf_aigw_analyzer.cli._common import ConfigOption, console, load


def serve(
    config: ConfigOption = None,
    host: str = typer.Option(None, "--host"),
    port: int = typer.Option(None, "--port"),
    reload: bool = typer.Option(
        False, "--reload", help="Enable uvicorn auto-reload for development."
    ),
) -> None:
    """Start the FastAPI control plane on 127.0.0.1 with a fixed default port."""

    if reload:
        console.print(
            "[red]--reload 当前不支持。[/red]"
            " 该命令直接传入已构建的 FastAPI app；请使用外部 uvicorn 命令做开发热重载。"
        )
        raise typer.Exit(code=2)

    settings = load(config)
    bind_host = host or settings.control.host
    bind_port = port if port is not None else settings.control.port

    try:
        import uvicorn

        from cf_aigw_analyzer.control.app import build_app
    except ImportError as exc:  # pragma: no cover - import guard
        console.print(f"[red]缺少 FastAPI/uvicorn 依赖: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    app = build_app(settings=settings)
    console.print(f"启动 control plane: [bold]http://{bind_host}:{bind_port}[/bold]")
    uvicorn.run(
        app, host=bind_host, port=bind_port, reload=reload, log_level=settings.logging.level.lower()
    )
