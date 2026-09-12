# Deployment and Environments — the AWS path

> **This is not the default path, and the commands below no longer run as
> written.** It documents the four-environment AWS deployment the template
> used before [ADR-009](../docs/adr/ADR-009-one-backend-deployable.md): Lambda
> for the API and the MCP server, AgentCore Runtime for the agent, Terraform
> for everything else.
>
> The `make api-deploy` / `agent-deploy` / `mcp-deploy` / `web-deploy` and
> `make deploy-*` targets were removed with that change, and the scripts they
> called — now in `advanced/scripts/deploy/` — still address `services/api`,
> `services/agent` and `services/mcp`, which no longer exist. The Terraform
> under `advanced/infra/` is intact and still valid.
>
> Read this for the wiring and the sequencing rationale. Expect to rewrite the
> parts that name services before running any of it. The current, working path
> is [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).


## Environments

```text
local
dev
staging
prod
```

`local` is disposable.

`dev`, `staging`, and `prod` are isolated cloud environments.

Never share databases, buckets, secrets, or auth configuration across prod and non-prod.

---

# Terraform Layout

```text
infra/terraform/
├── modules/
│   ├── networking/     VPC, subnets, security groups
│   ├── database/       RDS Postgres, credentials in Secrets Manager
│   ├── storage/        S3, optional DynamoDB
│   ├── api/            ECR, Lambda, HTTP API Gateway, IAM
│   ├── mcp/            ECR, Lambda, Function URL, IAM
│   └── observability/  alarms, metric filters, dashboard
└── envs/
    ├── local/          LocalStack; only the services it reproduces well
    ├── dev/
    ├── staging/
    └── prod/
```

Each environment composes the shared modules and supplies its own sizing.
Production variables carry `validation` blocks that refuse a CORS wildcard,
single-AZ, a backup window under seven days, or deletion protection turned off —
so a dangerous configuration fails at plan time rather than in review.

Example:

```text
envs/staging/main.tf
envs/staging/variables.tf
envs/staging/outputs.tf
envs/staging/backend.tf
```

Prefer separate remote state per environment.

Do not use the same state file for staging and production.

---

# What Terraform Owns

Terraform owns conventional AWS infrastructure:

- API Gateway,
- Lambda,
- IAM,
- S3,
- DynamoDB if used,
- database/networking resources,
- CloudWatch alarms/log configuration,
- DNS where appropriate,
- environment-specific outputs.

## What Terraform does not own

**Application image tags.** Terraform creates the Lambda functions and ignores
`image_uri` thereafter. `make api-deploy` builds an immutable image, pushes it
and repoints the function. A release is therefore not an infrastructure change:
`terraform plan` stays free of churn from ordinary deploys, and rollback is
"point at the previous tag".

**AgentCore Runtime.** Owned by the AgentCore CLI. Terraform outputs the API
URL, MCP endpoint and bucket name; `scripts/deploy/agent.sh` reads them and
passes them to `agentcore deploy`. See
[ADR-006](../docs/adr/ADR-006-agentcore-owns-its-own-resources.md).

**The web host.** Deliberately unchosen — Next.js deploys well to several
places and the right answer depends on the product. `scripts/deploy/web.sh`
fails with instructions until `WEB_DEPLOY_COMMAND` is configured, rather than
silently doing nothing.

One system owns each resource. Two systems owning one resource is not a
theoretical concern: it surfaced immediately while building this template, as a
"table already exists" error when the local Terraform environment and the
Compose bootstrap both tried to create the same DynamoDB table.

---

# AgentCore Deployment

```bash
make agent-deploy ENV=staging
```

`scripts/deploy/agent.sh` reads the Terraform outputs for that environment,
exports them, and runs `agentcore configure` then `agentcore deploy --dry-run`
then `agentcore deploy`. The handoff between the two systems is explicit and in
version control, not a manual step somebody remembers.

It requires the AgentCore CLI and fails with an install hint when it is missing:

```bash
uv tool install bedrock-agentcore-starter-toolkit
```

---

# Environment Configuration

Terraform creates the database credential itself — a generated password stored
in Secrets Manager at `/<project>/<environment>/database-url`. It is never a
Terraform variable, so it cannot end up in a tfvars file, a shell history or a
CI log.

```text
/ai-agent-saas/dev/database-url
/ai-agent-saas/staging/database-url
/ai-agent-saas/prod/database-url
```

The API's Lambda role can read exactly that one secret, and nothing else.

`WORKOS_CLIENT_ID` is passed as plain configuration, deliberately: it only
identifies which JWKS to verify access tokens against. The **API key is never
given to the API** — it verifies tokens rather than calling WorkOS, so it does
not need one.

Never reuse WorkOS production credentials locally.

Recommended:

```text
WorkOS dev environment      → local/dev
WorkOS staging environment  → staging
WorkOS prod environment     → prod
```

---

# Dev Deployment

Branch:

```text
dev
```

Manual fallback:

```bash
git checkout dev
git pull origin dev

make check
make deploy-dev
```

Conceptual deploy:

```text
terraform plan/apply dev
deploy FastAPI Lambda
deploy AgentCore agent
deploy MCP service/targets
deploy web
run smoke tests
```

---

# Staging Deployment

Branch:

```text
staging
```

Promotion:

```bash
git checkout staging
git pull origin staging
git merge origin/dev
git push origin staging
```

CI:

```text
test
eval
Terraform plan
Terraform apply staging
deploy services
smoke tests
E2E
```

Staging is the primary release-candidate and validation environment.

Keep it seeded, observable, and reliable.

---

# Production Deployment

Branch:

```text
main
```

Promotion:

```bash
git checkout main
git pull origin main
git merge origin/staging
git push origin main
```

Production pipeline:

```text
required CI
↓
production Terraform plan
↓
human approval
↓
database migration
↓
Terraform apply
↓
service deploys
↓
agent deploy
↓
web deploy
↓
smoke tests
↓
release tag
```

---

# Rollback Strategy

Every deployable component should have a rollback story.

### Web

Redeploy previous build/version.

### FastAPI Lambda

Point alias back to previous Lambda version or redeploy previous artifact.

### Agent

Keep previous known-good agent artifact/config and redeploy it.

### Database

Prefer forward-compatible migrations.

Do not rely on destructive down migrations as the primary production rollback plan.

### Infrastructure

Review Terraform plans carefully. Re-applying old code is not guaranteed to reverse every infrastructure mutation safely.

---

# Database Migrations

Recommended pattern:

```text
expand
deploy compatible app
migrate data
contract later
```

Avoid schema changes that require all services to switch atomically.

---

# CI/CD Mapping

```text
.github/workflows/
├── ci.yml              every PR and push: lint, types, unit, contracts-in-sync,
│                       terraform fmt/validate, integration; evals and E2E when
│                       targeting staging or main
├── deploy.yml          reusable pipeline, called by the three below
├── deploy-dev.yml      push to dev
├── deploy-staging.yml  push to staging, then staging-check
└── deploy-prod.yml     push to main, behind the protected environment
```

## Credentials

Deploys assume a role via GitHub OIDC. There are no long-lived AWS access keys
in GitHub secrets.

Per environment, configure:

| Kind | Name | Purpose |
|---|---|---|
| secret | `AWS_DEPLOY_ROLE_ARN` | role assumed via OIDC |
| secret | `TF_STATE_BUCKET` | remote state bucket |
| secret | `TF_LOCK_TABLE` | state lock table |
| secret | `WORKOS_CLIENT_ID` | that environment's WorkOS client |
| variable | `AWS_REGION`, `CORS_ORIGINS`, `APP_URL` | non-sensitive configuration |
| variable | `WEB_DEPLOY_COMMAND` | your web host's deploy command |

Use GitHub Environments named `dev`, `staging` and `production`, and put
required reviewers on `production` — `deploy.yml` runs `terraform plan` before
the gate, so a human sees the plan before the apply.

---

# Deployment Commands

Human-friendly commands:

```bash
make deploy-dev
make deploy-staging
make deploy-prod
```

Lower-level:

```bash
make terraform-plan ENV=staging
make terraform-apply ENV=staging
make api-deploy ENV=staging
make agent-deploy ENV=staging
make mcp-deploy ENV=staging
make web-deploy ENV=staging
make smoke ENV=staging
```

Production commands should require an explicit environment and confirmation in CI.

---

# Staging Validation

Before validating a staging release:

```bash
git checkout staging
git pull
make smoke ENV=staging
make staging-check ENV=staging
```

`staging-check` should validate:

- web loads,
- login works,
- agent responds,
- streaming works,
- MCP tools work,
- map renders,
- test itinerary can be created,
- persistence works,
- observability/traces are available.

Have deterministic fallback fixture data so a third-party event API outage does not block end-to-end validation.
