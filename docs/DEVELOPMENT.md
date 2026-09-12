# Development Guide

## Tooling

Recommended:

```text
Node package manager     pnpm
Python package manager   uv
Containers               Docker Compose
Task runner              Make
Infrastructure           Terraform (only for the advanced/ AWS path)
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

Variables are grouped by concern in `.env.example`: APP, WORKOS, DATABASE,
AGENT, ANTHROPIC, MODEL PROVIDER, MCP, MAPS, and the event/place providers.

Important ones:

| Variable | Notes |
|---|---|
| `APP_ENV` | `local`, `dev`, `staging` or `prod`. Several safety guards key off it. |
| `AUTH_DEV_FIXTURE` | `1` uses a deterministic local identity instead of WorkOS. Refused unless `APP_ENV=local`. |
| `AGENT_MODEL_PROVIDER` | `anthropic` or `scripted`. `scripted` skips model inference; refused unless `APP_ENV=local`. |
| `PLACES_PROVIDER` / `EVENTS_PROVIDER` | `fixture` (deterministic dataset) or `http` (a real provider). |
| `DATABASE_URL` | Plain `postgresql://`; the app derives asyncpg and psycopg forms. `DATABASE_SYNC_URL` optionally overrides the sync one. |

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
Secrets Manager, and the deployed services read configuration from their
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
uv sync --project services/backend
```

---

# Local Infrastructure

Use Docker Compose for dependencies that are convenient to run locally:

```text
postgres
optional redis
```

Example:

```bash
docker compose up -d postgres
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

# AWS emulation

The default path uses no AWS services. The `advanced/` Terraform path still
validates against LocalStack; see [advanced/README.md](../advanced/README.md).

---

# Agent Development

The agent is mounted on the backend at `/agent`, so it starts with everything
else:

```bash
make backend-dev
curl http://localhost:8000/agent/ping
```

To exercise it directly, POST an AG-UI `RunAgentInput` to
`/agent/invocations` and read the SSE stream. The web app does this through the
CopilotKit runtime route, which is also where the caller's identity is attached
— the agent never trusts a client-supplied one.

With `AGENT_MODEL_PROVIDER=scripted` there is no model call at all, which is
what makes the end-to-end suite and the evals free and deterministic.

---

## Choosing a model

`AGENT_MODEL_PROVIDER` picks what interprets requests and writes replies:

| Provider | Needs | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` (or `ant auth login`) | Least setup. Default model `claude-opus-5`; set `ANTHROPIC_MODEL_ID` to `claude-sonnet-5` or `claude-haiku-4-5` to spend less. |
| `scripted` | nothing | No model call. Local and test only. |

The model does two short jobs per run — turning a sentence into constraints,
and a two- or three-sentence reply — so cost is dominated by which model you
choose rather than which platform serves it. Everything else (planner, tools,
streaming, authorization) is identical across providers.

---

# MCP Development

The MCP server is mounted on the backend at `/mcp`:

```bash
make backend-dev
```

Point any MCP client at `http://localhost:8000/mcp` — that is the same URL a
deployed Claude Desktop config would use, which is the whole reason the tools
sit behind the protocol rather than being called directly.

If a client gets a 421, the transport is rejecting its `Host` header. Add the
host to `MCP_ALLOWED_HOSTS`; it is DNS-rebinding protection, not a bug.

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
make backend-dev
```

That serves the composed application — the API, the agent and the MCP server
(ADR-009). To run *only* the API, without the agent or MCP mounted:

```bash
cd services/backend
uv run fastapi dev app/main.py
```

Useful when debugging a route in isolation; note that `/agent` and `/mcp` are
absent, so the web app's assistant will not work against it.

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
Terminal 3  make backend-dev
```

For convenience:

```bash
make dev
```

starts all three in one terminal, prefixing each line with its service name.
**Ctrl-C stops everything** — the script puts each service in its own process
group so the signal reaches the whole tree (make → uv → uvicorn/next), not just
the wrapper.

If a server is ever left holding a port — a hard `kill -9`, a crashed terminal —
reclaim them with:

```bash
make dev-stop
```

---

# Docker

Each independently deployable service should have a Dockerfile even if its production target does not require a long-running container.

Suggested:

```text
apps/web/Dockerfile
services/backend/Dockerfile
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
docker compose build backend
docker compose up -d backend
```

The recommended local loop is different from either: `make infra-up` runs only
Postgres in a container, and `make dev` runs the application
services natively. Native processes restart faster and attach to a debugger more
easily; the Dockerfiles exist for CI parity, container deployment and for
reproducing a dependency problem that only appears in an image.

The agent is included in Compose so `docker compose up` yields a complete
working stack. The API, the agent and the MCP server are one container
(ADR-009), reachable at `/`, `/agent` and `/mcp` on port 8000.

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

Migrations use the synchronous driver while the application uses asyncpg;
both derive from `DATABASE_URL`, so deploy tooling never needs an event loop.

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
make backend-dev

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

make deploy-help

# only for the advanced/ AWS path
make terraform-fmt
make terraform-validate
make infra-check
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
