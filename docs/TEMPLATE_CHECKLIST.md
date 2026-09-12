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
