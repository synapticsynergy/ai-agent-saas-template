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

| What | Where |
|---|---|
| Permission helpers | `services/api/tests/test_permissions.py` |
| Configuration guards | `services/api/tests/test_config.py` |
| Access-token verification | `services/api/tests/test_workos_auth.py` |
| Geospatial helpers | `packages/contracts/tests/test_geo.py` |
| Candidate scoring, budget allocation | `services/agent/tests/test_scoring.py` |
| Itinerary construction | `services/agent/tests/test_planner.py` |
| Request parsing, revision | `services/agent/tests/test_parse_and_replan.py` |
| Web formatting and state narrowing | `apps/web/src/lib/*.test.ts` |

None of these need a container, a network or a model.

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

Live in `services/api/tests/test_plan_service.py` and `test_routes.py`.

```python
async def test_viewer_cannot_create_a_plan(session, viewer):
    with pytest.raises(PermissionDenied):
        await plan_service.create_plan(session, viewer, sample_plan())
```

Authorization is deterministic and testable without an HTTP client and without
a model. Note the shape: services take a `Principal` and derive the tenant from
it, so there is no code path that accepts an `organization_id` from a caller.

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

Live in `services/mcp/tests/`. Every tool is called directly — no LLM, no MCP
transport — and asserted on its contract.

```text
search_places(valid)                → schema-conforming results, deterministic
search_places(tiny radius)          → zero results, not an error
search_events(inverted window)      → invalid_arguments
provider timeout                    → provider_timeout, retryable=true
provider failure                    → provider_error,   retryable=false
save_plan(no identity)              → not_authenticated
save_plan(viewer)                   → permission_denied, retryable=false
save_plan(member)                   → persisted, and the token is forwarded verbatim
save_plan(repeat, same key)         → one plan, not two
```

The retryable flag matters: it is how the agent distinguishes "try again" from
"you are not allowed", without parsing prose.

---

# 4. Agent Evaluations

Do not assert exact prose.

Evaluate capabilities.

The dataset is `evals/dataset.json`; the evaluators are `evals/evaluators.py`.

```json
{
  "id": "reference_request",
  "input": "Plan my evening near me. I want dinner, live music, and drinks. Keep it walkable and under $100.",
  "expectations": {
    "uses_tools": ["search_places", "search_events", "build_route"],
    "includes_categories": ["dinner", "music", "drinks"],
    "max_total_cost": 100,
    "max_walk_km": 2.0,
    "min_stops": 3,
    "itinerary_is_feasible": true
  }
}
```

Because the fixture providers are deterministic, the suite is safe to gate CI
on at a 100% threshold.

Implemented evaluators:

| Evaluator | Checks |
|---|---|
| `uses_tools` / `forbidden_tools` | the agent reached for the right capabilities |
| `includes_categories` / `forbidden_categories` | the plan matches what was asked |
| `max_total_cost` / `max_walk_km` / `min_stops` | stated constraints were honoured |
| `itinerary_is_feasible` | stops are ordered, do not overlap, and leave travel time |
| `no_hallucinated_stops` | every stop traces back to a tool result |
| `cheaper_than_previous` / `shorter_walk_than_previous` | a revision actually revised |
| `save_denied` / `save_succeeds` / `authorization_respected` | the permission boundary held, and a denial is never reported as success |
| `run_completes` | the stream terminated |

Two of these caught real defects that no prose assertion would have: a flat
over-budget penalty that made the agent pick the *most* expensive unaffordable
venue, and preference tags used as a hard filter, which discarded every
affordable option.

Run with `make eval`, or a single case with:

```bash
uv run --project services/agent python -m evals.run --case replan_under_tighter_budget
```

---

# 5. Integration Tests

Run real service boundaries against local infrastructure.

Live in `tests/integration/`. They require real local infrastructure and
**refuse to run without it** rather than skipping — a green run has to mean the
boundaries were exercised.

```bash
make infra-up
make test-integration
```

| File | Exercises |
|---|---|
| `test_postgres.py` | tenant isolation, cascades, idempotency against real Postgres |
| `test_s3.py` | tenant key prefixing and not-found mapping against LocalStack |
| `test_api_http.py` | the ASGI app end to end, including a forged `organization_id` in the body |
| `test_mcp_server.py` | a live MCP server over streamable HTTP: handshake, tool schemas, the `ui://` resource, and an unauthenticated `save_plan` |

The MCP server is launched as a subprocess in its own uv project, because it
cannot share a virtualenv with the rest of the suite — the Strands SDK pins
`mcp<2.2` while the server needs `mcp>=2.2`. That mirrors how it deploys: a
separate deployable with its own dependencies.

---

# 6. End-to-End Tests

Test user-visible flows.

Recommended browser framework: Playwright.

Live in `tests/e2e/specs/`, run with Playwright on both a desktop and a phone
viewport.

```bash
make infra-up
make dev            # in another terminal
make e2e-install    # once
make test-e2e
```

`planner.spec.ts` walks the reference flow from
[REFERENCE_APP.md](REFERENCE_APP.md): request a plan, watch progress stream,
render the itinerary and map, replan conversationally, approve, save, and
retrieve the saved plan through the deterministic API. `smoke.spec.ts` is the
smaller suite `make smoke ENV=staging` runs against a deployed environment.

Specs select on `data-testid`, not on MUI's DOM shape, so a component refactor
does not break them.

Point at a deployed environment with `E2E_BASE_URL`.

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
