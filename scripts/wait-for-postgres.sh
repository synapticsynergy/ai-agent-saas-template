#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo -n "==> waiting for postgres"
for _ in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -q 2>/dev/null; then
    echo " ready"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "ERROR: postgres did not become ready within 60s. Check 'docker compose logs postgres'." >&2
exit 1
