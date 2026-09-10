#!/usr/bin/env bash
# Release-candidate validation for a deployed environment.
# Extends the smoke test with the agent, streaming, MCP and persistence paths.
set -euo pipefail
ENV_NAME="${1:?usage: staging-check.sh <env>}"
cd "$(dirname "$0")/.."

./scripts/smoke.sh "$ENV_NAME"

echo "==> agent evaluation suite"
uv run --project services/agent python -m evals.run --threshold "${EVAL_THRESHOLD:-0.8}"

echo "==> end-to-end suite against $ENV_NAME"
E2E_BASE_URL="${E2E_BASE_URL:-${NEXT_PUBLIC_APP_URL:-}}" pnpm --filter e2e test

echo ""
echo "staging-check passed for $ENV_NAME"
