# Testing Strategy

Agentic SaaS needs both conventional software tests and agent evaluations.

## Layers

```text
                    E2E
               Integration Tests
                 Agent Evals
              MCP / Tool Contracts
             Auth / Service Tests
                 Unit Tests
```

---

# 1. Unit Tests

Test deterministic functions without infrastructure.

Examples:

- route scoring,
- budget calculation,
- distance formatting,
- Pydantic validation,
- permission helpers,
- data transformations.

Python:

```bash
uv run pytest tests/unit
```

Web:

```bash
pnpm --dir apps/web test
```

---

# 2. Service Tests

Test FastAPI service/business logic.

Example:

```python
async def test_viewer_cannot_save_plan():
    user = make_user(permissions=["plans:read"])

    with pytest.raises(PermissionDenied):
        await plan_service.save_plan(user=user, plan=...)
```

Authorization should be deterministic.

---

# 3. Tool Contract Tests

Every tool should be independently testable without the LLM.

Test:

- input validation,
- output schema,
- timeout behavior,
- provider error mapping,
- authorization,
- tenant scope,
- idempotency.

Example scenarios:

```text
search_events(valid location)       → results
search_events(provider timeout)     → typed retryable error
save_plan(viewer)                   → forbidden
save_plan(member)                   → persisted
get_plan(other organization)        → not found/forbidden
```

---

# 4. Agent Evaluations

Do not assert exact prose.

Evaluate capabilities.

Reference dataset:

```json
{
  "input": "Plan an inexpensive evening with live jazz and food",
  "expectations": {
    "uses_event_search": true,
    "uses_place_search": true,
    "max_budget": 100,
    "includes_live_music": true
  }
}
```

Possible evaluators:

- task completion,
- required tool usage,
- forbidden tool usage,
- tool argument quality,
- itinerary feasibility,
- budget compliance,
- groundedness,
- authorization compliance,
- trajectory length,
- latency,
- cost.

Track eval results over time.

---

# 5. Integration Tests

Run real service boundaries against local infrastructure.

Local test topology:

```text
test runner
   ├→ FastAPI
   ├→ Postgres container
   ├→ LocalStack
   └→ MCP server
```

Use LocalStack for applicable AWS integration behavior.

Examples:

- file upload → local S3,
- Lambda integration,
- DynamoDB persistence,
- API Gateway config,
- Terraform resource creation.

Run:

```bash
make test-integration
```

---

# 6. End-to-End Tests

Test user-visible flows.

Recommended browser framework: Playwright.

Reference E2E:

```text
login
  ↓
open planner
  ↓
submit "plan my evening"
  ↓
observe streamed progress
  ↓
map/itinerary renders
  ↓
ask "make it cheaper"
  ↓
plan updates
  ↓
save
  ↓
saved plan appears
```

Run:

```bash
make test-e2e
```

Use deterministic provider fixtures for CI where practical.

Keep a smaller smoke suite against real staging integrations.

---

# Streaming Tests

Test that streaming starts before completion.

Assertions can include:

```text
first event arrives
tool-start event arrives
text/state deltas arrive
final event arrives
connection closes cleanly
```

Also test:

- agent error mid-stream,
- tool error mid-stream,
- user cancellation,
- browser reconnect where supported.

---

# Security Tests

Minimum cases:

```text
unauthenticated API request              → 401
authenticated wrong org                  → denied
viewer write                             → denied
member allowed action                    → allowed
LLM-supplied forged organization_id      → ignored/denied
LLM requests unauthorized tool           → denied
approved-but-unauthorized action         → denied
```

The prompt is not a security control.

---

# Infrastructure Tests

Run:

```bash
terraform fmt -check -recursive infra/terraform
terraform validate
```

Optionally apply relevant modules to LocalStack:

```bash
make infra-local-apply
```

In CI:

```text
terraform fmt
terraform validate
plan dev/staging
policy/security scanning if added
```

Production `apply` requires protected branch/release approval.

---

# CI Gates

## Feature PR → dev

Required:

```text
lint
typecheck
unit
service tests
tool contract tests
Terraform fmt/validate
```

## dev → staging

Add:

```text
integration tests
agent eval suite
E2E against deploy preview/dev
```

## staging → main

Add:

```text
staging smoke tests
critical agent eval threshold
Terraform production plan review
manual approval
```

---

# Useful Commands

```bash
make lint
make typecheck
make test-unit
make test-integration
make test-e2e
make eval
make test
make check
```

`make test` should run the full local suite that is reasonable on a developer machine.

`make check` should run the fast pre-push suite.
