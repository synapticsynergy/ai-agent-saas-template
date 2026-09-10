# Development Guide

## Tooling

Recommended:

```text
Node package manager     pnpm
Python package manager   uv
Containers               Docker Compose
AWS local emulator       LocalStack
Agent local runtime      AgentCore CLI
Infrastructure           Terraform
Task runner              Make
```

## Environment Files

One `.env` at the repository root configures every service:

```bash
cp .env.example .env
```

The API, agent and MCP server read it through pydantic-settings. The Next.js app
reads it too — `next.config.ts` loads the root file explicitly, because Next only
looks in its own directory by default.

Values already present in the environment win, so a shell override or a
container's `env_file` still takes precedence.

Never commit actual secrets. `.env` is git-ignored; only `.env.example` is
tracked.

Variables are grouped by concern in `.env.example`: APP, WORKOS, AWS, DATABASE,
AGENTCORE, BEDROCK, MCP, MAPS, and the event/place providers.

Important ones:

| Variable | Notes |
|---|---|
| `APP_ENV` | `local`, `dev`, `staging` or `prod`. Several safety guards key off it. |
| `AUTH_DEV_FIXTURE` | `1` uses a deterministic local identity instead of WorkOS. Refused unless `APP_ENV=local`. |
| `AGENT_MODEL_PROVIDER` | `bedrock` or `scripted`. `scripted` skips model inference; refused unless `APP_ENV=local`. |
| `PLACES_PROVIDER` / `EVENTS_PROVIDER` | `fixture` (deterministic dataset) or `http` (a real provider). |
| `AWS_ENDPOINT_URL` | Points the AWS SDK at LocalStack. Must be **empty** in deployed environments — the API refuses to start otherwise. |
| `DATABASE_URL` / `DATABASE_SYNC_URL` | asyncpg for the application, psycopg for Alembic. |

### Startup validation

Configuration is validated eagerly, so a misconfigured deployment fails at
startup with a readable error rather than at the first request that needs the
value. For example, with `APP_ENV=staging` and no WorkOS configuration:

```text
Invalid API configuration:
  APP_ENV=staging requires these variables to be set: WORKOS_API_KEY, WORKOS_CLIENT_ID
```

### Cloud environments

Do not use a `.env` file. Terraform writes the database connection strings to
Secrets Manager, and the Lambda functions read configuration from their
environment. See [DEPLOYMENT.md](DEPLOYMENT.md).

---

# First-Time Setup

```bash
git clone <repo-url>
cd ai-agent-saas-template

cp .env.example .env

make install
make infra-up
make db-migrate
make dev
```

## `make install`

Expected to run approximately:

```bash
pnpm --dir apps/web install
uv sync --project services/api
uv sync --project services/agent
uv sync --project services/mcp
```

---

# Local Infrastructure

Use Docker Compose for dependencies that are convenient to run locally:

```text
postgres
localstack
optional redis
```

Example:

```bash
docker compose up -d postgres localstack
```

or:

```bash
make infra-up
```

Stop:

```bash
make infra-down
```

Reset:

```bash
make infra-reset
```

Logs:

```bash
docker compose logs -f
```

---

# LocalStack

Use LocalStack for conventional AWS resources where emulation improves the dev/test loop:

- S3
- DynamoDB
- Lambda
- API Gateway
- SQS/SNS if added later
- Terraform validation against a local AWS-compatible endpoint

Do not make the project dependent on LocalStack for AgentCore behavior.

Recommended Terraform flow:

```bash
lstk terraform -chdir=infra/terraform/envs/local init
lstk terraform -chdir=infra/terraform/envs/local plan
lstk terraform -chdir=infra/terraform/envs/local apply
```

If local Terraform does not add value for a particular project, Docker Compose + application-level configuration is acceptable.

---

# Agent Development

Run the agent locally using AgentCore CLI:

```bash
cd services/agent
agentcore dev
```

Run with logs:

```bash
agentcore dev --logs
```

Invoke the local dev server with streaming:

```bash
agentcore dev "Plan a simple evening" --stream
```

The exact CLI arguments can evolve, so keep this document aligned with the AgentCore CLI version pinned by the project.

---

# MCP Development

Run the MCP server independently:

```bash
cd services/mcp
uv run python server.py
```

or:

```bash
make mcp-dev
```

Keep MCP tools testable without the LLM.

Example:

```python
async def test_search_events():
    result = await search_events(
        latitude=45.52,
        longitude=-122.68,
        start_at=...
    )
    assert result.items
```

---

# FastAPI Development

```bash
cd services/api
uv run fastapi dev app/main.py
```

Expected local endpoint:

```text
http://localhost:8000
```

Health route:

```bash
curl http://localhost:8000/health
```

---

# Web Development

```bash
cd apps/web
pnpm dev
```

Expected:

```text
http://localhost:3000
```

---

# Full Local Development

Recommended terminals:

```text
Terminal 1  docker compose up
Terminal 2  pnpm dev
Terminal 3  uv run fastapi dev
Terminal 4  agentcore dev --logs
Terminal 5  MCP server
```

For convenience:

```bash
make dev
```

should start or coordinate the common processes.

---

# Docker

Each independently deployable service should have a Dockerfile even if its production target does not require a long-running container.

Suggested:

```text
apps/web/Dockerfile
services/api/Dockerfile
services/agent/Dockerfile
services/mcp/Dockerfile
```

Goals:

- reproducible dependencies,
- easy local testing,
- CI parity,
- optional container deployment,
- easier debugging.

Build all:

```bash
make build          # docker compose build
```

Run everything in containers:

```bash
docker compose up
```

Rebuild a service:

```bash
docker compose build api
docker compose up -d api
```

The recommended local loop is different from either: `make infra-up` runs only
Postgres and LocalStack in containers, and `make dev` runs the application
services natively. Native processes restart faster and attach to a debugger more
easily; the Dockerfiles exist for CI parity, container deployment and for
reproducing a dependency problem that only appears in an image.

The agent is included in Compose so `docker compose up` yields a complete
working stack without the AgentCore CLI installed. For work that needs AgentCore
Runtime parity, use `make agent-dev` instead.

---

# Database Migrations

Pick one migration tool and standardize it.

For SQLAlchemy projects, Alembic is a conventional choice.

Commands:

```bash
make db-migration NAME="add plans table"   # autogenerate a revision
make db-migrate                            # apply to head
make db-rollback                           # step back one revision
```

Migrations use the synchronous driver (`DATABASE_SYNC_URL`) while the
application uses asyncpg, so deploy tooling never needs an event loop.

Do not apply production schema changes from developer laptops.

Production migrations should run in a controlled deploy step.

---

# Seed Data

Provide deterministic demo fixtures:

```bash
make seed
```

Seed:

- demo organization,
- demo users/roles where possible,
- user preferences,
- example saved plan,
- mocked event/location fixtures for tests.

Avoid making the live demo completely dependent on a flaky third-party service.

---

# Recommended Make Targets

```text
make install
make dev
make web-dev
make api-dev
make agent-dev
make mcp-dev

make infra-up
make infra-down
make infra-reset
make infra-local-apply

make lint
make typecheck
make test
make test-unit
make test-integration
make test-e2e
make eval

make db-migrate
make seed

make terraform-fmt
make terraform-validate
make infra-check

make deploy-dev
make deploy-staging
make deploy-prod
```

The Makefile is the human-friendly interface; underlying tools remain directly usable.

---

# Fast Feedback Loop

While coding:

```bash
make lint
make test-unit
```

Before pushing:

```bash
make check
```

Expected `make check`:

```text
format check
lint
typecheck
unit tests
tool contract tests
Terraform formatting/validation
```

Before merge to staging:

```bash
make test
make eval
```
