#!/usr/bin/env bash
# Post-deploy smoke test. Verifies a deployed environment is reachable and
# healthy. Reads endpoints from Terraform outputs for the environment.
set -euo pipefail
ENV_NAME="${1:?usage: smoke.sh <env>}"
cd "$(dirname "$0")/.."

TF_DIR="infra/terraform/envs/${ENV_NAME}"

tf_output() {
  terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null || true
}

API_URL="${SMOKE_API_URL:-$(tf_output api_base_url)}"
WEB_URL="${SMOKE_WEB_URL:-${NEXT_PUBLIC_APP_URL:-}}"

if [ -z "$API_URL" ]; then
  echo "ERROR: could not resolve the API URL for '$ENV_NAME'." >&2
  echo "       Run 'make terraform-apply ENV=$ENV_NAME' first, or set SMOKE_API_URL." >&2
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
[ -n "$WEB_URL" ] && check "web root" "$WEB_URL"

exit "$fail"
