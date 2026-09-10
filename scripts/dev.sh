#!/usr/bin/env bash
# Run the whole local stack in one terminal. Ctrl-C stops every child.
#
# Job control (`set -m`) is what makes that work: without it, background jobs
# share this script's process group, so signalling "the group" hits this script
# and nothing else — Ctrl-C then kills the wrapper and orphans four servers
# still holding their ports. With it, each `&` job leads its own group and
# `kill -- -$pid` reaches the whole tree (make → uv → uvicorn/next).
set -uo pipefail
set -m

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
stopping=0

stop() {
  # Ctrl-C reaches every process in the foreground group, so children may
  # already be on their way out; this makes the shutdown deterministic either
  # way, and guards against running twice.
  [ "$stopping" -eq 1 ] && return 0
  stopping=1
  trap - INT TERM EXIT

  echo ""
  echo "==> stopping"

  # Bash narrates "Terminated: 15" for each job as it reaps it. That is noise
  # during an intentional shutdown, so stderr is parked for the duration.
  # Progress messages below go to stdout and are unaffected.
  exec 3>&2 2>/dev/null

  for pid in "${pids[@]:-}"; do
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done

  # Give them a moment, then insist. A dev server that ignores TERM would
  # otherwise keep its port and break the next `make dev`.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    still_running=0
    for pid in "${pids[@]:-}"; do
      kill -0 "$pid" 2>/dev/null && still_running=1
    done
    [ "$still_running" -eq 0 ] && break
    sleep 0.5
  done

  for pid in "${pids[@]:-}"; do
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  done

  wait || true

  exec 2>&3 3>&-
  echo "==> stopped"
}

# Ctrl-C is the documented way to stop this, so it exits 0. Reporting a signal
# as a failure would make every normal shutdown look like something broke.
on_signal() {
  stop
  exit 0
}

trap on_signal INT TERM
trap stop EXIT

start() {
  local label="$1"; shift
  echo "==> starting $label"
  ( "$@" 2>&1 | sed "s/^/[$label] /" ) &
  pids+=("$!")
}

start api   make api-dev
start mcp   make mcp-dev
start agent make agent-dev
start web   make web-dev

cat <<'MSG'

  web    http://localhost:3000
  api    http://localhost:8000/health
  agent  http://localhost:8080/health
  mcp    http://localhost:8090/mcp

  Ctrl-C to stop everything.

MSG

wait
