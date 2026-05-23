#!/usr/bin/env bash
# Docker / bare-metal entrypoint for cloudflare-ai-gateway-analyzer.
#
# Usage:
#   ./entrypoint.sh serve         # default — start FastAPI control plane
#   ./entrypoint.sh sync ...      # one-shot sync
#   ./entrypoint.sh <subcommand>  # any cli.py subcommand
set -euo pipefail

cd "$(dirname "$0")"

# Make sure SQLite directory exists. The schema is created lazily on first DB
# connect, so we just ensure the path is writable.
mkdir -p "${CF_AIGW_STORAGE__DATA_DIR:-./local/data}"

CMD="${1:-serve}"
shift || true

case "$CMD" in
  serve)
    exec python serve.py "$@"
    ;;
  sync)
    exec python cli.py sync "$@"
    ;;
  sync-usage)
    exec python cli.py sync-usage "$@"
    ;;
  status|query|init|config|version|vacuum|accounts|gateways)
    exec python cli.py "$CMD" "$@"
    ;;
  *)
    # Forward everything else to the CLI so future subcommands work without
    # editing this script.
    exec python cli.py "$CMD" "$@"
    ;;
esac
