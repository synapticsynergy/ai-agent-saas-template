# New Project Checklist

Use this after creating a repository from the template.

## Rename

- [ ] application name
- [ ] package names
- [ ] Terraform state/resource prefixes
- [ ] AWS account/region defaults
- [ ] WorkOS environment/configuration
- [ ] domains
- [ ] README demo/use case

## Product

- [ ] define primary job-to-be-done
- [ ] define one reference agent workflow
- [ ] define user input
- [ ] define structured output
- [ ] define human approval points
- [ ] decide whether MCP App UI adds value

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
- [ ] AgentCore local dev command
- [ ] seed fixtures
- [ ] one-command startup

## Tests

- [ ] unit tests
- [ ] service/auth tests
- [ ] tool contract tests
- [ ] agent eval dataset
- [ ] integration tests
- [ ] E2E smoke flow
- [ ] authorization eval cases
- [ ] streaming tests

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
