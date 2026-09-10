#!/usr/bin/env bash
# Run the agent locally.
#
# Prefers the AgentCore CLI when it is installed, because that reproduces the
# AgentCore Runtime contract (session headers, /invocations, /ping). Falls back
# to running the same ASGI app under uvicorn so the template is usable without
# the CLI. Both serve the identical FastAPI app from services/agent/agent.py.
set -euo pipefail
cd "$(dirname "$0")/../services/agent"

if command -v agentcore >/dev/null 2>&1 && [ "${AGENT_DEV_FORCE_UVICORN:-0}" != "1" ]; then
  echo "==> agentcore dev (AgentCore CLI $(agentcore --version 2>/dev/null || echo '?'))"
  exec agentcore dev --logs
fi

echo "==> uvicorn fallback (AgentCore CLI not found; see docs/DEVELOPMENT.md)"
exec uv run uvicorn agent:app --host 0.0.0.0 --port "${AGENT_PORT:-8080}" --reload
