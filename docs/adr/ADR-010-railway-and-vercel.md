# ADR-010: Railway and Vercel, three environments, no AWS on the default path

**Status:** Accepted — amends [ADR-009](ADR-009-one-backend-deployable.md); supersedes [ADR-004](ADR-004-localstack-scope.md) for the default path

## Context

ADR-009 collapsed the backend into one container and offered Fly or Render as
hosts. Neither models environments well: Fly needs one app and config per
environment, Render one blueprint entry per environment. The repository's git
workflow promises `dev → staging → main` with a deploy per branch, and nothing
implemented that.

The default path also still carried AWS: LocalStack in compose and CI, S3 and
DynamoDB adapters used only by the readiness probe, a Bedrock model provider,
and a Terraform CI job for code that had moved to `advanced/`.

## Decision

- **Railway hosts the backend.** Environments are first-class: `dev`,
  `staging` and `production` each hold the backend service and their own
  Postgres, and each tracks the branch of the same name. `railway.json` is the
  service definition; its pre-deploy command runs Alembic so the schema leads
  the code.
- **Vercel hosts the web app**, Production on `main`, previews with
  branch-scoped variables for `dev` and `staging`.
- **One `DATABASE_URL`.** The backend accepts a plain `postgresql://` URL and
  derives the asyncpg and psycopg forms. `DATABASE_SYNC_URL` is an optional
  override.
- **The AWS remnants leave the default path**: LocalStack, the S3 and DynamoDB
  adapters, the Bedrock provider, and the Terraform CI job. They are preserved
  under `advanced/` and in git history.

## Consequences

- A new environment is a dashboard duplicate plus one typed secret.
- No GitHub Actions deploy workflow. CI gates merges; the hosts deploy.
- The Anthropic API is the only real model provider on the default path.
- Object storage, when a product needs it, is a new decision — not a
  half-wired S3 adapter.
- `advanced/` is now further from the default path; anyone graduating to it
  restores the adapters from history rather than flipping a flag.
