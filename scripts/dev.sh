#!/usr/bin/env bash
# Run the whole local stack in one terminal. Ctrl-C stops every child process.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found. Run 'make env' first (or: cp .env.example .env)." >&2
  exit 1
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -q '^postgres$'; then
  echo "Local infrastructure is not running. Start it with 'make infra-up'." >&2
  exit 1
fi

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    kill -TERM "-$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

start() {
  local label="$1"; shift
  echo "==> starting $label"
  ( set -m; "$@" 2>&1 | sed -u "s/^/[$label] /" ) &
  pids+=("$!")
}

start api   make api-dev
start mcp   make mcp-dev
start agent make agent-dev
start web   make web-dev

echo ""
echo "  web    http://localhost:3000"
echo "  api    http://localhost:8000/health"
echo "  agent  http://localhost:8080/health"
echo "  mcp    http://localhost:8090/mcp"
echo ""

wait
