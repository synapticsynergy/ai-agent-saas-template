#!/usr/bin/env bash
# Run Alembic migrations against a deployed environment's database.
#
# Migrations run from CI (or a bastion/VPC-attached runner), never from a
# developer laptop against dev/staging/prod — see docs/DEVELOPMENT.md.
ENV_NAME="${1:?usage: migrate.sh <env>}"
source "$(dirname "$0")/_shared.sh"

if [ "$ENV_NAME" != "local" ] && [ "${CI:-}" != "true" ] && [ "${ALLOW_LOCAL_MIGRATION:-0}" != "1" ]; then
  echo "ERROR: refusing to migrate '$ENV_NAME' outside CI." >&2
  echo "       Production schema changes belong in a controlled deploy step." >&2
  echo "       Set ALLOW_LOCAL_MIGRATION=1 only for a deliberate break-glass run." >&2
  exit 1
fi

DATABASE_SYNC_URL="${DATABASE_SYNC_URL:-$(tf_output database_url)}"
if [ -z "$DATABASE_SYNC_URL" ]; then
  echo "ERROR: DATABASE_SYNC_URL is not set and Terraform exposes no database_url output." >&2
  exit 1
fi

export DATABASE_SYNC_URL
cd services/api
uv run alembic upgrade head
echo "migrations applied to $ENV_NAME"
