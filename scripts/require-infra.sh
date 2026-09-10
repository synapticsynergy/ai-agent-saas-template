#!/usr/bin/env bash
# Integration tests need real local infrastructure. Fail loudly rather than
# silently skipping, so a green run always means the boundaries were exercised.
set -euo pipefail
cd "$(dirname "$0")/.."

missing=()
docker compose ps --status running --services 2>/dev/null | grep -q '^postgres$'   || missing+=("postgres")
docker compose ps --status running --services 2>/dev/null | grep -q '^localstack$' || missing+=("localstack")

if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: integration tests require local infrastructure: ${missing[*]}" >&2
  echo "       Start it with: make infra-up" >&2
  exit 1
fi
