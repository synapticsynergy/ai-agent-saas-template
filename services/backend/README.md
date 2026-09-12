# Backend

One deployable serving three things that used to be three services
([ADR-009](../../docs/adr/ADR-009-one-backend-deployable.md)):

| Mount | Package | Owns |
|---|---|---|
| `/plans`, `/agent-runs`, `/users/me`, `/health` | `app` | Persistence, tenancy, authorization |
| `/agent` | `agent_app` | The model loop, streaming AG-UI over SSE |
| `/mcp` | `mcp_server` | Agent-facing capabilities over MCP |

`asgi.py` composes them. They remain three independent packages — none imports
another except through HTTP or the shared contracts — so splitting them back
into separate deployables is a configuration change, not a refactor.

```bash
make backend-dev     # all three on :8000
make db-migrate
make db-migration NAME="add something"
make seed
make eval
```

---

## The application API

### Where authorization lives

`app/auth/permissions.py` defines one primitive:

```python
require_permission(principal, "plans:write")
```

Application code authorizes on permission slugs, never on role names. Roles are
just a convenient way to assign a permission set in WorkOS; adding one must
never require touching authorization logic.

Checks happen in two places, deliberately:

- **Routes** give an early, cheap 403.
- **Services** re-check, so a caller arriving another way — an MCP tool, a
  background job, a test — cannot bypass it by forgetting a decorator.

That second check is why sharing a process with the agent and the MCP server
changes nothing about the guarantee.

### Tenancy

Every service function takes a `Principal` and derives `organization_id` from
it. No function accepts an `organization_id` parameter, and no create or update
schema has the field. A model that invents one has nowhere to put it: the value
is dropped at validation.

A plan belonging to another organization raises `NotFound`, not
`PermissionDenied` — a 403 would confirm the id exists.

### Identity

The API never sees a WorkOS session cookie. Callers forward the AuthKit access
token as `Authorization: Bearer <jwt>`, and `app/auth/workos.py` verifies the
signature against the WorkOS JWKS. Nothing is trusted because of where it came
from — including a caller from inside this same process.

### Routes

```text
GET    /health              liveness
GET    /health/ready        readiness, per-dependency, 503 when degraded
GET    /users/me            the caller's organization, role and permissions
GET    /plans               tenant-scoped list
GET    /plans/{id}          404 across organizations
POST   /plans               requires plans:write; idempotent on a supplied key
PATCH  /plans/{id}          requires plans:write
DELETE /plans/{id}          requires plans:delete
POST   /agent-runs          requires agents:run
POST   /agent-runs/{id}/complete
GET    /agent-runs/{id}
```

Domain exceptions map to HTTP in one place (`app/main.py`), so services never
import `HTTPException` and stay usable from tools and tests.

---

## The agent

### What runs where

| Concern | Where it lives | Why |
|---|---|---|
| Interpreting the request | `agent_app/interpreter.py` | Language understanding is what a model is for. |
| Choosing venues, timing, budget | `agent_app/workflows/planner.py` | Deterministic, testable, auditable. |
| Reaching tools | `agent_app/tools/mcp_client.py` over MCP | Portable capability boundary (ADR-003). |
| Deciding if a write is allowed | the application API | The model is not a security boundary. |

### The model's job

Two things, and only two: turn a sentence into a `PlanningRequest`, and write
the two- or three-sentence reply about the finished plan. It is asked for
structured output on the first, so a malformed answer fails at the schema
boundary rather than becoming a strange itinerary.

Two things it is deliberately not allowed to decide, re-pinned after every call
whatever it returns:

- **where the user is** — that comes from the browser,
- **what time it is** — that comes from the server.

A model failure degrades to rule-based extraction rather than failing the run,
so a provider outage costs understanding, not availability. That fallback is
also a hazard worth knowing about: a request rejected with a 400 looks exactly
like an outage, which is why no sampling parameter is sent by default — current
Claude models reject them, and the run would silently stop using the model.

The planner is deliberately model-free. That is not a limitation — it is the
template's central principle applied to the agent itself: keep the
nondeterministic surface small, and everything you would want to test, audit or
explain stays ordinary code.

### Choosing a model

`AGENT_MODEL_PROVIDER` picks what interprets requests and writes replies:

| Provider | Needs | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` (or `ant auth login`) | The default. Least setup. Model `claude-opus-5`; set `ANTHROPIC_MODEL_ID` to `claude-sonnet-5` or `claude-haiku-4-5` to spend less. |
| `bedrock` | AWS credentials, plus model access granted in the Bedrock console | Keeps inference inside your AWS account. Uses the Mantle (Messages API) endpoint, so `BEDROCK_MODEL_ID` takes the `anthropic.`-prefixed form. |
| `scripted` | nothing | No model call, no spend. Local and test only; refused outside `APP_ENV=local`. |

Both providers go through the Anthropic SDK, so everything above the model —
prompts, structured output, fallbacks, re-pinning — is identical.

### HTTP contract

| Route | Purpose |
|---|---|
| `POST /agent/invocations` | Run the agent. Accepts AG-UI `RunAgentInput`, returns an AG-UI SSE stream. |
| `POST /agent/` | Same handler, so CopilotKit's `HttpAgent` can point at the mount root. |
| `GET /agent/ping` | Health probe. |

The caller's WorkOS access token arrives as `Authorization: Bearer <jwt>` and is
forwarded unchanged to the tool layer, which forwards it to the application API.
The agent holds no credential of its own for tenant operations.

---

## The MCP server

### What belongs here

Capabilities that earn a protocol boundary: reusable, independently deployable,
useful to more than one agent
([ADR-003](../../docs/adr/ADR-003-mcp-for-agent-tools.md)). Internal helpers —
scoring, geometry, formatting — stay ordinary Python.

| Tool | Consequential | Identity required |
|---|---|---|
| `search_places` | no | no |
| `search_events` | no | no |
| `get_place_details` | no | no |
| `build_route` | no | no |
| `save_plan` | **yes** | **yes** |
| `render_itinerary` | no | no |

Tool signatures are flat rather than taking a nested payload object: a model
picks arguments far more reliably from a flat schema, and the typed contracts in
`saas_contracts.tools` still do the validating.

### Why it is worth the indirection

Sharing a process with the agent means MCP buys nothing *here* over calling
these functions directly. What it buys is every other client: the same endpoint
works from Claude Desktop, VS Code, or any MCP host, with no extra code. If a
downstream product never needs that, calling the tool functions directly is the
honest simplification.

### This server is not a security boundary

`save_plan` extracts the caller's bearer assertion and forwards it to the
application API, which verifies the signature and checks `plans:write`. The MCP
server makes no authorization decision of its own, so there is exactly one place
that can be wrong. It holds no credential of its own either.

### Reaching it

The transport rejects unlisted `Host` headers with a 421 — DNS-rebinding
protection. `MCP_ALLOWED_HOSTS` names the hosts to accept, and configuration
refuses to start outside `local` without it, because the failure mode is
otherwise a server that silently refuses every client.

### Providers

Places, events and routing sit behind `Protocol` interfaces with a deterministic
fixture default. The fixture re-anchors its dataset on whatever coordinate is
requested, so it is not tied to any one city. Swap a provider by editing
`mcp_server/providers/registry.py`; nothing else changes.

Every automated test runs against the fixtures, so results are exact and no test
depends on a third party.

### MCP App

`ui://itinerary/map` is a `text/html;profile=mcp-app` resource bound to
`render_itinerary`. See
[REFERENCE_APP.md](../../docs/REFERENCE_APP.md#mcp-app) for what host support
currently allows.
