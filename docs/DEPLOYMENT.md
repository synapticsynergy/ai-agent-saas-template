# Deployment

Three environments, three branches, two hosts. Push to a branch and its
environment deploys.

| Branch    | Backend (Railway environment) | Web (Vercel)             | `APP_ENV` |
|-----------|-------------------------------|--------------------------|-----------|
| `dev`     | `dev`                         | preview, branch `dev`    | `dev`     |
| `staging` | `staging`                     | preview, branch `staging`| `staging` |
| `main`    | `production`                  | Production               | `prod`    |

The backend — API, agent and MCP server, one ASGI application
([ADR-009](adr/ADR-009-one-backend-deployable.md)) — runs as one Railway
service per environment, with a Railway Postgres beside it. The web app is one
Vercel project. Nothing here needs an AWS account; that path lives under
[`advanced/`](../advanced/README.md).

## 1. Railway: first environment

1. **New Project → Deploy from GitHub repo**, pick this repository. Railway
   reads `railway.json` and builds `services/backend/Dockerfile` with the
   repository root as context. Name the service `backend`.
2. **+ New → Database → PostgreSQL** in the same environment.
3. On the `backend` service, **Variables**:

   | Variable            | Value                                   |
   |---------------------|-----------------------------------------|
   | `APP_ENV`           | `prod`                                  |
   | `DATABASE_URL`      | `${{Postgres.DATABASE_URL}}`            |
   | `MCP_ALLOWED_HOSTS` | `${{RAILWAY_PUBLIC_DOMAIN}}`            |
   | `API_CORS_ORIGINS`  | your production web URL                 |
   | `WORKOS_API_KEY`    | from WorkOS                             |
   | `WORKOS_CLIENT_ID`  | from WorkOS                             |
   | `ANTHROPIC_API_KEY` | secret                                  |

   `${{...}}` are Railway reference variables; only the last row is typed.
   `AGENT_MODEL_PROVIDER` defaults to `anthropic`.
4. **Settings → Networking → Generate Domain**. That hostname is what
   `MCP_ALLOWED_HOSTS` resolves to.
5. Rename the environment to `production` and confirm it tracks `main`
   (**Settings → Environment**).

Every deploy runs `alembic upgrade head` first (`preDeployCommand` in
`railway.json`), so the schema always leads the code that reads it. A failed
migration blocks the deploy; the previous version keeps serving.

## 2. Railway: staging and dev

**Environments → + New Environment → Duplicate `production`**, named
`staging`, tracking branch `staging`. Repeat for `dev`. Duplicating copies the
variables and provisions a fresh Postgres per environment; change `APP_ENV`
and `API_CORS_ORIGINS` in each copy. Secrets are shared by the copy — rotate
the Anthropic key per environment if you want separate spend tracking.

Then create the branches:

```bash
git checkout main && git pull
git branch dev && git branch staging
git push origin dev staging
```

## 3. Vercel

Connect the repository once; `vercel.json` carries the monorepo build wiring.
Production tracks `main`. Every other branch deploys as a preview; `dev` and
`staging` get stable aliases of the form
`<project>-git-<branch>-<team>.vercel.app`.

**Settings → Environment Variables.** Set the Production values, then add the
same names for Preview scoped to branch `staging`, and again scoped to `dev`:

| Variable                | Production            | Preview `staging`       | Preview `dev`           |
|-------------------------|-----------------------|-------------------------|-------------------------|
| `APP_ENV`               | `production`          | `staging`               | `dev`                   |
| `API_BASE_URL`          | production backend URL| staging backend URL     | dev backend URL         |
| `AGENT_BASE_URL`        | `<API_BASE_URL>/agent`| same pattern            | same pattern            |
| `NEXT_PUBLIC_APP_URL`   | production web URL    | staging branch alias    | dev branch alias        |
| `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_REDIRECT_URI`, `WORKOS_COOKIE_PASSWORD` | per WorkOS environment | per WorkOS environment | per WorkOS environment |

`NEXT_PUBLIC_*` variables are inlined at **build** time; changing one needs a
redeploy. `WORKOS_REDIRECT_URI` must exactly match what WorkOS has configured
for that environment: `<NEXT_PUBLIC_APP_URL>/auth/callback`.

## 4. Verify each environment

```bash
SMOKE_API_URL=https://<backend-host> SMOKE_WEB_URL=https://<web-host> make smoke ENV=staging
```

or by hand:

```bash
curl https://<backend-host>/health
curl https://<backend-host>/agent/ping
curl -i https://<backend-host>/mcp        # 400 = reachable; 421 = MCP_ALLOWED_HOSTS is wrong
```

Then point an MCP client at the deployed server and confirm the same tools your
chat UI uses are listed:

```json
{
  "mcpServers": {
    "plan-my-evening": { "url": "https://<backend-host>/mcp" }
  }
}
```

### `MCP_ALLOWED_HOSTS` is not optional

The MCP transport rejects any `Host` header it was not told to expect with a
421 — DNS-rebinding protection. `${{RAILWAY_PUBLIC_DOMAIN}}` keeps it correct;
if you add a custom domain, add it here too (comma-separated).

### Sleeping is the thing to watch

Railway's trial and hobby plans can sleep an idle service. A browser tolerates
the cold start; an MCP client such as Claude Desktop, which connects on its own
schedule, reads it as a broken server. If the MCP endpoint matters, keep the
service always-on (**Settings → App Sleeping** off).

## Order of operations

Migrations → backend → web, and Railway does the first two for you. The web app
reads `API_BASE_URL` at request time, so it can deploy against a backend that
is already up.

## Rollback

| Layer    | How |
|----------|-----|
| Web      | Vercel keeps every deployment — promote the previous one. |
| Backend  | Railway **Deployments → ⋯ → Redeploy** on the previous deployment. |
| Database | `alembic downgrade -1`, only when the migration is genuinely reversible. Prefer rolling forward. |

Because migrations run ahead of the code, rolling the backend back one release
is safe: the schema is a superset of what the older code expects.

## Promotion

`dev → staging → main` by pull request, as in
[GIT_WORKFLOW.md](GIT_WORKFLOW.md). CI runs evals and end-to-end tests on PRs
into `staging` and `main`. After a staging deploy:

```bash
SMOKE_API_URL=https://<staging-backend> NEXT_PUBLIC_APP_URL=https://<staging-web> make staging-check ENV=staging
```
