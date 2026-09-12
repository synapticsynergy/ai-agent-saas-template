# Deployment

Two deploys. The web app goes to Vercel; the backend — the API, the agent and
the MCP server, which are one ASGI application
([ADR-009](adr/ADR-009-one-backend-deployable.md)) — goes to any host that runs
a container.

```
apps/web           → Vercel
services/backend   → Fly.io or Render
Postgres           → Neon (or any managed Postgres)
```

The AWS path — Terraform, Lambda, AgentCore, four environments — still exists
under [`advanced/`](../advanced/README.md), with
[advanced/DEPLOYMENT.md](../advanced/DEPLOYMENT.md) as its guide. Start here;
graduate when you have a reason.

## 1. Database

Create a Postgres database (Neon's free tier is enough to start) and keep two
connection strings — the app is async, Alembic is sync:

```bash
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DB
DATABASE_SYNC_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB
```

Apply migrations before the backend first starts:

```bash
cd services/backend && DATABASE_SYNC_URL=... uv run alembic upgrade head
```

Migrations run ahead of the code that reads the schema — expand first, contract
later — so a deploy never leaves the running version ahead of its database.

## 2. Backend

Both hosts build `services/backend/Dockerfile` with the repository root as the
build context, because the service depends on `packages/contracts` by path.

### Fly.io

```bash
fly launch --copy-config --no-deploy
fly secrets set \
  DATABASE_URL=... DATABASE_SYNC_URL=... \
  ANTHROPIC_API_KEY=... \
  WORKOS_API_KEY=... WORKOS_CLIENT_ID=...
fly deploy
```

`fly.toml` sets `auto_stop_machines = false` on purpose — see the note on
sleeping below.

### Render

New → Blueprint, pointed at this repository; `render.yaml` describes the
service. Set the secrets marked `sync: false` in the dashboard.

### Sleeping is the thing to watch

Free instances on both hosts sleep after inactivity and cold-start on the next
request. That is tolerable behind a browser. It is not tolerable for the MCP
endpoint: an MCP client such as Claude Desktop connects on its own schedule, and
a 50-second cold start reads as a broken server rather than a slow one. If the
MCP endpoint matters to you, pay for an always-on instance.

### `MCP_ALLOWED_HOSTS` is not optional

The MCP transport rejects any `Host` header it was not told to expect, with a
421 — DNS-rebinding protection. Set it to the hostname clients actually use:

```bash
MCP_ALLOWED_HOSTS=your-backend.fly.dev
```

Configuration refuses to start outside `APP_ENV=local` without it, because the
alternative failure mode is a server that runs happily and refuses every client.

## 3. Web

```bash
pnpm --filter web exec vercel deploy --prod
```

or connect the repository in Vercel's dashboard; `vercel.json` has the monorepo
build wiring. Set these in the Vercel project:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `API_BASE_URL` | `https://your-backend.fly.dev` |
| `AGENT_BASE_URL` | `https://your-backend.fly.dev/agent` |
| `NEXT_PUBLIC_APP_URL` | your Vercel URL |
| `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_REDIRECT_URI`, `WORKOS_COOKIE_PASSWORD` | from the WorkOS dashboard |

`NEXT_PUBLIC_*` variables are inlined at **build** time, so changing one
requires a redeploy, not just a restart.

`WORKOS_REDIRECT_URI` must exactly match the redirect configured in WorkOS —
`https://your-app.vercel.app/auth/callback`.

## 4. Verify

```bash
curl https://your-backend.fly.dev/health
curl https://your-backend.fly.dev/agent/ping
```

Then the part worth doing, because it is what the MCP boundary buys you — point
an MCP client at the deployed server and confirm the *same* tools your own chat
UI uses are available to it:

```json
{
  "mcpServers": {
    "plan-my-evening": {
      "url": "https://your-backend.fly.dev/mcp"
    }
  }
}
```

If the tools list is empty or every call fails, check `MCP_ALLOWED_HOSTS`
first — a 421 is the usual cause.

## Order of operations

Migrations → backend → web. The web app reads `API_BASE_URL` at request time, so
it can be deployed against a backend that is already up; doing it the other way
means a window where the UI points at nothing.

## Rollback

| Layer | How |
|---|---|
| Web | Vercel keeps every deployment — promote the previous one. |
| Backend | `fly releases` / `fly deploy --image <previous>`; Render has a rollback button. |
| Database | `alembic downgrade -1`, and only when the migration is genuinely reversible. Prefer rolling forward. |

Because migrations are applied ahead of the code, rolling the backend back one
release is safe: the schema is a superset of what the older code expects.
