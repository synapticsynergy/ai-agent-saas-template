#!/usr/bin/env bash
# Stop anything left listening on the development ports.
#
# `make dev` cleans up after itself, but a hard kill (or an older version of the
# dev script) can leave a server holding a port. This reclaims them.
set -uo pipefail

PORTS=(3000 8000)
found=0

for port in "${PORTS[@]}"; do
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  [ -z "$pids" ] && continue

  found=1
  echo "==> port $port: stopping $(echo "$pids" | tr '\n' ' ')"
  # shellcheck disable=SC2086
  kill -TERM $pids 2>/dev/null || true
done

if [ "$found" -eq 0 ]; then
  echo "Nothing listening on ${PORTS[*]}."
  exit 0
fi

# Give them a moment to exit cleanly, then insist.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  remaining=""
  for port in "${PORTS[@]}"; do
    remaining+="$(lsof -ti:"$port" 2>/dev/null || true)"
  done
  [ -z "$remaining" ] && { echo "All development ports are free."; exit 0; }
  sleep 0.5
done

for port in "${PORTS[@]}"; do
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  [ -z "$pids" ] && continue
  echo "==> port $port did not stop; forcing"
  # shellcheck disable=SC2086
  kill -KILL $pids 2>/dev/null || true
done

echo "All development ports are free."
