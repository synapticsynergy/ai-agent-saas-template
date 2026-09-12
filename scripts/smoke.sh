#!/usr/bin/env bash
# Post-deploy smoke test. Verifies a deployed environment is reachable and
# healthy.
#
# Set SMOKE_API_URL (and optionally SMOKE_WEB_URL) to point it at a deployment.
# On the advanced/ AWS path the URLs come from Terraform outputs instead, which
# is why the fallback is still here.
set -euo pipefail
ENV_NAME="${1:?usage: smoke.sh <env>}"
cd "$(dirname "$0")/.."

TF_DIR="advanced/infra/terraform/envs/${ENV_NAME}"

tf_output() {
  [ -d "$TF_DIR" ] || return 0
  command -v terraform >/dev/null 2>&1 || return 0
  terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null || true
}

API_URL="${SMOKE_API_URL:-$(tf_output api_base_url)}"
WEB_URL="${SMOKE_WEB_URL:-${NEXT_PUBLIC_APP_URL:-}}"

if [ -z "$API_URL" ]; then
  echo "ERROR: could not resolve the API URL for '$ENV_NAME'." >&2
  echo "       Set SMOKE_API_URL, e.g.:" >&2
  echo "         SMOKE_API_URL=https://your-backend.fly.dev make smoke ENV=$ENV_NAME" >&2
  echo "       (On the advanced/ AWS path, 'make terraform-apply ENV=$ENV_NAME' provides it.)" >&2
  exit 1
fi

fail=0
check() {
  local label="$1" url="$2" expect="${3:-200}"
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" || echo 000)"
  if [ "$code" = "$expect" ]; then
    echo "  ok    $label ($code) $url"
  else
    echo "  FAIL  $label (expected $expect, got $code) $url"
    fail=1
  fi
}

echo "==> smoke test: $ENV_NAME"
check "api health"            "$API_URL/health"
check "api requires auth"     "$API_URL/plans" 401
check "agent health"          "$API_URL/agent/ping"
# 400 is the streamable-HTTP transport rejecting a bare GET, which is what a
# reachable MCP server does. 421 instead means MCP_ALLOWED_HOSTS does not list
# this hostname — the usual reason a deployed MCP server refuses every client.
check "mcp reachable"         "$API_URL/mcp" 400
[ -n "$WEB_URL" ] && check "web root" "$WEB_URL"

exit "$fail"
