#!/usr/bin/env bash
# The end-to-end suite drives the real application. Fail loudly when it is not
# running rather than reporting a green suite that tested nothing.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${E2E_BASE_URL:-http://localhost:3000}"

if ! curl -sf -o /dev/null --max-time 5 "$BASE_URL"; then
  echo "ERROR: no application at $BASE_URL." >&2
  echo "       Start the stack with: make infra-up && make dev" >&2
  echo "       Or point at a deployed environment with E2E_BASE_URL." >&2
  exit 1
fi

# Next.js compiles a route on its first request in development, which can take
# longer than a test's timeout. Warm the routes the suite visits so the first
# spec is not racing the compiler.
echo -n "==> warming routes"
for path in "/" "/planner" "/plans" "/api/copilotkit/info"; do
  curl -sf -o /dev/null --max-time 90 "$BASE_URL$path" || true
  echo -n "."
done
echo " ready"
