# New Project Checklist

Use this after creating a repository from the template.

## Verify it runs first

```bash
cp .env.example .env
make install
make infra-up
make dev
```

Open <http://localhost:3000>, plan an evening, save it. That exercises
authentication, the agent, streaming, MCP tools, authorization and persistence
in one pass. Fix anything broken here before renaming things.

## Rename

- [ ] application name — `apps/web/src/app/layout.tsx` metadata, `AppShell`
- [ ] Terraform `project` variable in each `advanced/infra/terraform/envs/*/variables.tf`
- [ ] AWS region defaults in the same files
- [ ] WorkOS environment per deployment (never reuse production credentials)
- [ ] domains and `CORS_ORIGINS`
- [ ] README demo/use case
- [ ] `packages/contracts` package name, if you publish it

## Replace the reference application

The "Plan My Evening" implementation is a worked example, not scaffolding to
build around. Replacing it means:

- [ ] define the primary job-to-be-done
- [ ] define one reference agent workflow
- [ ] replace the domain contracts in `packages/contracts/src/saas_contracts/`
- [ ] replace the deterministic workflow in `services/backend/agent_app/workflows/`
- [ ] replace the tools in `services/backend/mcp_server/tools/`
- [ ] replace the fixture dataset in `saas_contracts/fixtures/data.json`
- [ ] define your human approval points
- [ ] decide whether an MCP App UI adds value for your domain

What to keep: the auth layer, the permission model, the service/route split, the
identity propagation chain, the streaming vocabulary, and the test structure.

### Where the reference application actually lives

About 58 files mention the evening-planning domain, so this is not a layer you
peel off — it is most of the repository's substance. There is deliberately no
`make new-app` that deletes it for you: the result would not compile, and a
half-stripped repository is harder to work in than a complete example you edit
in place. Build your domain by replacing these, one at a time, keeping the
suite green as you go.

**Replace wholesale** — nothing here survives a change of domain:

```text
packages/contracts/src/saas_contracts/plan.py     the domain types
packages/contracts/src/saas_contracts/fixtures/   the canned dataset
services/backend/agent_app/workflows/             scoring, planning, revision
services/backend/mcp_server/tools/                the tools themselves
services/backend/mcp_server/resources/            the ui:// MCP App document
services/backend/app/models/plan.py               the tables
services/backend/app/schemas/plan.py
services/backend/app/services/plan_service.py
services/backend/app/routes/plans.py
services/backend/app/seed.py
services/backend/alembic/versions/                start a fresh migration
apps/web/src/components/Itinerary*.tsx            the domain UI
apps/web/src/components/Planner*.tsx
apps/web/src/hooks/usePlannerAgent.ts
apps/web/src/lib/itinerary.ts
apps/web/src/app/(map)/planner/                   the routes
apps/web/src/app/(standard)/plans/
evals/dataset.json                                your cases, your checks
tests/e2e/specs/planner.spec.ts
```

**Keep as-is** — this is the actual template:

```text
services/backend/asgi.py                          the composition
services/backend/app/auth/                        WorkOS, permissions, principals
services/backend/app/persistence/                 engine, session, S3, Dynamo
services/backend/app/main.py                      error mapping, correlation ids
services/backend/agent_app/asgi.py                the AG-UI contract
services/backend/agent_app/streaming.py           the event vocabulary
services/backend/agent_app/tools/mcp_client.py    token forwarding
services/backend/mcp_server/providers/            the registry pattern
services/backend/mcp_server/context.py            identity extraction
apps/web/src/lib/{auth,api,env}.ts                the server-only boundary
apps/web/src/middleware.ts
apps/web/src/app/api/copilotkit/                  identity injection
apps/web/src/theme/                               the design system
```

**Edit, do not delete** — these mix the two, and the domain parts are obvious:

```text
services/backend/agent_app/runner.py              orchestration + intent routing
services/backend/agent_app/interpreter.py         prompts are domain, plumbing is not
services/backend/agent_app/narration.py
services/backend/mcp_server/server.py             registration + tool signatures
apps/web/src/lib/format.ts                        currency/time helpers are reusable
apps/web/src/components/AppShell.tsx              navigation names your routes
apps/web/src/app/page.tsx                         the landing copy
```

## Auth

- [ ] organization model
- [ ] default roles
- [ ] permission slugs
- [ ] protected routes
- [ ] tenant-scoped persistence
- [ ] tool authorization

## Agent

- [ ] agent system prompt
- [ ] model selection
- [ ] max execution/timeout
- [ ] tool list
- [ ] retry policy
- [ ] memory policy
- [ ] streaming events
- [ ] cancellation behavior

## MCP

For every proposed MCP capability ask:

- [ ] Does this need to be reusable outside one agent?
- [ ] Does this benefit from independent deployment?
- [ ] Is the latency/complexity worth it?
- [ ] Does it expose an MCP App?
- [ ] How is identity propagated?
- [ ] Where is authorization enforced?

## Persistence

- [ ] choose Postgres/DynamoDB based on access patterns
- [ ] create migrations
- [ ] add `organization_id`
- [ ] define backup/restore
- [ ] configure S3 if blobs/files are required

## Local Development

- [ ] `.env.example`
- [ ] Dockerfiles
- [ ] `docker-compose.yml`
- [ ] Postgres container
- [ ] LocalStack if useful
- [ ] the backend's local dev command
- [ ] seed fixtures
- [ ] one-command startup

## Tests

The template ships all of these; the work is retargeting them at your domain.

- [ ] unit tests for your deterministic logic
- [ ] service tests asserting tenant isolation and permission checks
- [ ] tool contract tests, including provider failure mapping
- [ ] agent eval dataset for your workflow
- [ ] integration tests against real infrastructure
- [ ] E2E happy path
- [ ] authorization eval cases (viewer cannot write, wrong org cannot read)
- [ ] streaming tests asserting events arrive before completion

Keep the property the template's suites have: **assert on structured outcomes,
never on prose.** Every real defect found while building this template was
caught by an assertion on a number or a code, not on wording.

## IaC

- [ ] dev
- [ ] staging
- [ ] prod
- [ ] separate state
- [ ] Terraform fmt/validate
- [ ] deployment outputs
- [ ] IAM least privilege
- [ ] secrets/config
- [ ] observability

## CI/CD

- [ ] feature PR checks
- [ ] dev deployment
- [ ] staging deployment
- [ ] production approval
- [ ] smoke tests
- [ ] release tag

## Reference Application

- [ ] staging seed data
- [ ] end-to-end reference flow
- [ ] architecture diagram
- [ ] trace/eval view
- [ ] third-party API fallback data
- [ ] operational runbook
