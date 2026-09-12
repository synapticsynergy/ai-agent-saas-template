# Advanced: the AWS deployment path

Everything here was the template's *only* deployment path. It is preserved, not
deprecated — but it is no longer what you get by default, because it made the
first deploy expensive ([ADR-009](../docs/adr/ADR-009-one-backend-deployable.md)).

```
advanced/
├── infra/terraform/   VPC, RDS, S3, DynamoDB, IAM, API Gateway, CloudWatch
├── scripts/deploy/    per-service deploy scripts, and the migration runner
└── workflows/         GitHub Actions: deploy.yml + dev/staging/prod callers
```

## What the default path does instead

| Concern | Default | Here |
|---|---|---|
| Web | Vercel | Terraform output + `WEB_DEPLOY_COMMAND` |
| Backend | One container per environment on Railway | Lambda (API) + AgentCore (agent) + Lambda (MCP) |
| Database | Railway Postgres | RDS in a VPC |
| Environments | `dev`, `staging`, `production` | `local`, `dev`, `staging`, `prod` |
| IaC | none | Terraform, per-environment state |

The default path no longer ships the S3/DynamoDB adapters, the Bedrock model
provider or LocalStack ([ADR-010](../docs/adr/ADR-010-railway-and-vercel.md)).
They are still in git history: check out the commit before ADR-010 landed
(`git log --diff-filter=D -- services/backend/app/persistence/s3.py` finds it)
if you graduate to this path and need them.

## When to come back to it

Reach for this when you have a reason, not by default. Good reasons:

- **You need the workloads to scale independently.** A burst of agent traffic
  sharing a process with CRUD is a real constraint — eventually. ADR-001 makes
  this argument and is still worth reading.
- **You need failure isolation** between the agent and the API.
- **Compliance requires** a VPC, private subnets, or an audited IAM boundary.
- **You are already on AWS** and want one account, one bill, one IAM story.

## What graduating actually involves

Less than it looks, because the merge kept the seams. `app`, `agent_app` and
`mcp_server` are still independent packages and still talk over HTTP, so
splitting them is configuration:

1. Deploy the same image three times with different process commands.
2. Point `MCP_SERVER_URL` and `AGENT_BASE_URL` at the split deployments instead
   of at `localhost:8000`.

The parts that genuinely need work are the ones that were deleted rather than
moved: the Lambda container target and its Mangum handler, and the AgentCore
Runtime wiring. `git show v0.1.0-aws-full-stack` has both if you want them back.

The scripts in `scripts/deploy/` still assume that older layout — they deploy
`services/api`, `services/agent` and `services/mcp` as separate units, and
those directories no longer exist. Treat them as a reference for the Terraform
wiring rather than as runnable, and expect to rewrite the parts that name
services.
