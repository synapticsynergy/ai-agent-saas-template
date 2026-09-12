# Railway + Vercel, three environments

**Status:** approved design, sub-project 1 of 3
**Date:** 2026-09-11

Sub-projects, in order:

1. **This spec.** Deploy the backend to Railway and the web app to Vercel across
   `dev`, `staging` and `main`, and remove the AWS remnants from the default path.
2. WorkOS → Firebase Auth with a personal workspace per user. Separate spec.
3. Post-deploy smoke and promotion checks. Separate spec.

## Goal

A contributor pushes to `dev` and dev is deployed. `staging` and `main` behave
the same for their environments. A new environment needs one secret typed by a
human (the Anthropic key; later a Firebase key). Nothing in the default path
requires an AWS account.

## Non-goals

- Auth changes. WorkOS stays until sub-project 2, so its variables remain in the
  environment lists below.
- Custom domains.
- A GitHub Actions deploy workflow. Railway and Vercel deploy on branch push;
  CI remains the merge gate only.
- Any change under `advanced/`. It is the archived AWS path and stays as-is.

## Environments

| Branch    | Railway environment | Vercel                       | `APP_ENV` |
|-----------|---------------------|------------------------------|-----------|
| `dev`     | `dev`               | preview, branch-scoped vars  | `dev`     |
| `staging` | `staging`           | preview, branch-scoped vars  | `staging` |
| `main`    | `production`        | Production                   | `prod`    |

Every Railway environment holds two services:

- `backend` — built from `services/backend/Dockerfile`, root directory `/`
  (the build context must include `packages/contracts`). Serves the API, the
  agent and the MCP server on one port (ADR-009).
- `postgres` — Railway's managed Postgres. One per environment, so credentials
  never cross environments.

The `dev` and `staging` branches do not exist on `origin` yet. They are created
from `main` once this work lands, and the git workflow doc stays as written
(`feature/* → dev → staging → main`).

## Railway configuration as code

`railway.json` at the repository root, replacing `fly.toml` and `render.yaml`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "services/backend/Dockerfile"
  },
  "deploy": {
    "preDeployCommand": ["alembic upgrade head"],
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

- The Dockerfile's last stage is `runtime`, which is what a build without a
  target produces, so no target setting is needed.
- The pre-deploy command runs in the built image with the service's variables
  before the new version receives traffic. That is the "migrations ahead of
  code" rule with no script. The `runtime` stage must therefore contain Alembic,
  `alembic.ini` and the `alembic/` directory; verify and add them to the image
  if the stage currently omits them.
- `PORT` is honoured by the existing `CMD`.

### Variables per Railway environment

Set on the `backend` service. Reference variables (`${{...}}`) are filled by
Railway; only the last row is typed by hand.

| Variable            | Value                                     |
|---------------------|-------------------------------------------|
| `APP_ENV`           | `dev` / `staging` / `prod`                |
| `DATABASE_URL`      | `${{Postgres.DATABASE_URL}}`              |
| `MCP_ALLOWED_HOSTS` | `${{RAILWAY_PUBLIC_DOMAIN}}`              |
| `API_CORS_ORIGINS`  | the Vercel URL for that branch            |
| `WORKOS_API_KEY`, `WORKOS_CLIENT_ID` | from WorkOS (until sub-project 2) |
| `ANTHROPIC_API_KEY` | secret                                    |

`AGENT_MODEL_PROVIDER` defaults to `anthropic` and needs no setting.

## Code change: one `DATABASE_URL`

Railway (and every managed Postgres) provides `postgresql://user:pass@host/db`.
The app currently requires two variables with SQLAlchemy driver prefixes baked
in. Change both settings classes that read the database URL so that:

- `DATABASE_URL` accepts `postgresql://`, `postgres://`, `postgresql+asyncpg://`
  or `postgresql+psycopg://`.
- Two derived properties, `database_async_url` and `database_sync_url`, rewrite
  the scheme to `postgresql+asyncpg://` and `postgresql+psycopg://` respectively.
- `DATABASE_SYNC_URL` remains readable as an override for anyone who needs a
  different sync endpoint, but is no longer required anywhere: not in
  `.env.example`, CI, compose, Alembic's `env.py`, or the docs.

Alembic's `env.py`, the async engine factory, seeds and the integration test
setup switch to the derived properties. Behaviour with the old two-variable
setup is unchanged.

## Removals

All of the following leave the default path. Each already has an equivalent
under `advanced/` where it is still wanted.

| Remove                                              | Notes |
|-----------------------------------------------------|-------|
| `fly.toml`, `render.yaml`                           | replaced by `railway.json` |
| `localstack` service in `docker-compose.yml`, `scripts/localstack/`, LocalStack checks in `scripts/require-infra.sh` | compose becomes Postgres + backend + web |
| LocalStack service and `AWS_*`/`S3_BUCKET` env in `.github/workflows/ci.yml` | integration job keeps Postgres only |
| `terraform` job in CI                               | Terraform belongs to `advanced/`; `make infra-check` still runs it on demand |
| `app/persistence/s3.py`, `app/persistence/dynamo.py`, their tests | only consumer is the readiness check |
| `check_storage` from `/health/ready`                | readiness reports `database` only |
| `aws_*`, `s3_bucket`, `dynamodb_*` settings and the `AWS_ENDPOINT_URL` validator in `app/config.py` | |
| `bedrock` from `ModelProvider`, `bedrock_*` settings, the Bedrock branch in `agent_app/interpreter.py`, its tests | `ModelProvider` becomes `Literal["anthropic", "scripted"]` |
| `boto3`, `boto3-stubs`, and any Bedrock/Strands dependency used only by the Bedrock provider, from `services/backend/pyproject.toml`; regenerate `uv.lock` | keep anything the `anthropic` provider still needs |
| `AWS_*`, `DYNAMODB_*`, `BEDROCK_*`, `DATABASE_SYNC_URL` from `.env.example` | |
| `infra-up` starts Postgres only; help text updated | `infra-local-apply` and the `terraform-*` targets stay, since they already point at `advanced/` |

The e2e CI job and `docker-compose.yml`'s `backend` service lose their `AWS_*`
variables. `docs/DEVELOPMENT.md`'s environment tables drop the AWS and Bedrock
rows and the `scripted`/`bedrock` wording becomes `scripted`/`anthropic`.

## Vercel

One Vercel project connected to the repository; `vercel.json` is unchanged.
Production tracks `main`. `dev` and `staging` deploy as previews, and each gets
a stable branch alias (`<project>-git-dev-<team>.vercel.app`).

Preview variables are scoped by branch in the Vercel dashboard:

| Variable                          | `main` (Production)            | `staging` (Preview, branch `staging`) | `dev` (Preview, branch `dev`) |
|-----------------------------------|--------------------------------|---------------------------------------|-------------------------------|
| `APP_ENV`                         | `prod`                         | `staging`                             | `dev`                         |
| `API_BASE_URL`                    | production backend URL         | staging backend URL                   | dev backend URL               |
| `AGENT_BASE_URL`                  | `<API_BASE_URL>/agent`         | same pattern                          | same pattern                  |
| `NEXT_PUBLIC_APP_URL`             | production Vercel URL          | staging branch alias                  | dev branch alias              |
| `WORKOS_*` (four variables)       | per WorkOS environment         | per WorkOS environment                | per WorkOS environment        |

`NEXT_PUBLIC_*` values are inlined at build time; changing one means a redeploy.

## CI

`.github/workflows/ci.yml` keeps its shape. Changes:

- `integration` job: drop the LocalStack service and AWS variables; set only
  `DATABASE_URL` (plain `postgresql://`, exercising the new derivation).
- `e2e` job: same variable cleanup.
- Remove the `terraform` job.
- Triggers already cover `main`, `staging`, `dev` and PRs into them. Evals and
  e2e already gate PRs into `staging` and `main`. No change.

## Documentation

- `docs/DEPLOYMENT.md` — rewritten for this model: environments table, Railway
  setup, variable tables above, Vercel branch scoping, order of operations
  (Railway runs migrations for you), rollback (Railway redeploy of a previous
  deployment; Vercel promote), and the MCP host/421 note carried over.
- `docs/GIT_WORKFLOW.md` — unchanged in structure; the "deploys automatically"
  claims become true. Add one line naming the Railway environment each branch
  deploys to.
- `docs/DEVELOPMENT.md`, `README.md`, `docs/ARCHITECTURE.md` — remove Fly,
  Render, LocalStack, S3, DynamoDB and Bedrock mentions from the default path;
  point AWS readers at `advanced/`.
- `docs/adr/ADR-010-railway-and-vercel.md` — records: Railway replaces Fly and
  Render because environments are first-class; three environments map to three
  branches; the AWS adapters and Bedrock provider are removed from the default
  path and preserved under `advanced/`; one `DATABASE_URL` is derived into
  async and sync forms.
- `advanced/README.md` — one sentence noting that the default path no longer
  ships the S3/DynamoDB adapters or the Bedrock provider, and where the last
  version with them lives (this repo's git history at the merge commit).

## Verification

Automated, all must pass before this merges:

- `make check` (format, lint, types, contracts, unit).
- `make infra-up && make test-integration` with the new compose file.
- `docker compose up` brings up Postgres, backend and web; `/health/ready`
  returns `{"database": true}`.
- A unit test for the URL derivation covering all four accepted schemes and the
  `DATABASE_SYNC_URL` override.
- `grep -rn "boto3\|localstack\|bedrock\|fly.io\|render.yaml"` over everything
  outside `advanced/` and `docs/adr/` returns nothing.

Manual, done by the repository owner with their Railway and Vercel logins,
written into `docs/DEPLOYMENT.md` as a checklist:

1. Create the Railway project from the GitHub repo; add a Postgres service; set
   the variables table; confirm the environment is named `production` and
   tracks `main`.
2. Duplicate the environment as `staging` (tracks `staging`) and `dev` (tracks
   `dev`). Railway copies variables and creates a fresh Postgres in each.
3. Create the `dev` and `staging` branches from `main` and push them.
4. Connect the Vercel project; set the branch-scoped variables table.
5. `curl` `/health`, `/agent/ping` and `/mcp` (expect 400, not 421) on each
   backend; open each web URL.

## Risks

- **Pre-deploy command support.** If the Railway plan or region in use does not
  offer `preDeployCommand`, the fallback is a `start` wrapper that runs
  `alembic upgrade head` before `uvicorn`. Slightly less clean (a failed
  migration takes the instance down rather than blocking the deploy) but the
  same ordering guarantee. Decide during implementation by checking the
  dashboard, not by guessing.
- **Free-tier sleeping.** Same MCP caveat as before: an MCP client reads a cold
  start as a broken server. The deployment doc keeps the warning.
