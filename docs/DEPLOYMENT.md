# Deployment and Environments

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

Recommended:

```text
infra/terraform/
├── modules/
│   ├── api/
│   ├── database/
│   ├── storage/
│   ├── networking/
│   └── observability/
└── envs/
    ├── local/
    ├── dev/
    ├── staging/
    └── prod/
```

Each environment composes shared modules.

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

Terraform should own conventional AWS infrastructure:

- API Gateway,
- Lambda,
- IAM,
- S3,
- DynamoDB if used,
- database/networking resources,
- CloudWatch alarms/log configuration,
- DNS where appropriate,
- environment-specific outputs.

AgentCore infrastructure may be provisioned by the current supported AgentCore deployment tooling or Terraform where stable provider support exists for the exact resource. Avoid forcing one IaC tool to own a resource if the platform's supported deployment path is materially better.

Document ownership explicitly so resources are not managed by two deployment systems.

---

# AgentCore Deployment

Typical agent workflow:

```bash
cd services/agent

agentcore deploy --dry-run
agentcore deploy
agentcore status
agentcore invoke --prompt "smoke test"
```

Keep agent deployment commands wrapped by Make/CI:

```bash
make agent-deploy ENV=staging
```

AgentCore deployment and Terraform deployment should exchange outputs through environment configuration/CI rather than hidden manual steps.

---

# Environment Configuration

Suggested secret/config naming:

```text
/ai-agent-saas/dev/...
/ai-agent-saas/staging/...
/ai-agent-saas/prod/...
```

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

Recommended GitHub Actions:

```text
ci.yml
  pull requests
  lint/typecheck/tests/terraform validate

deploy-dev.yml
  push to dev

deploy-staging.yml
  push to staging

deploy-prod.yml
  push to main
  protected environment approval
```

Use GitHub Environments:

```text
development
staging
production
```

Store only environment-specific deployment secrets in the associated protected environment.

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
