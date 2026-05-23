"""Launch the local Streamlit dashboard."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def build_streamlit_command(
    db_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    account_id: str | None = None,
    gateway_id: str | None = None,
    gateway_name: str | None = None,
) -> list[str]:
    app_path = Path(__file__).with_name("dashboard_app.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--",
        "--db",
        str(Path(db_path).expanduser().resolve()),
    ]
    if account_id:
        command.extend(["--account-id", account_id])
    if gateway_id:
        command.extend(["--gateway-id", gateway_id])
    if gateway_name:
        command.extend(["--gateway-name", gateway_name])
    return command


def run_dashboard(
    db_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    account_id: str | None = None,
    gateway_id: str | None = None,
    gateway_name: str | None = None,
) -> int:
    if importlib.util.find_spec("streamlit") is None:
        raise RuntimeError('dashboard 需要额外依赖：请先运行 pip install -e ".[dashboard]"')

    command = build_streamlit_command(db_path, host, port, account_id, gateway_id, gateway_name)
    print(f"本地看板: http://{host}:{port}")
    print("按 Ctrl+C 结束。")
    return subprocess.call(command)
