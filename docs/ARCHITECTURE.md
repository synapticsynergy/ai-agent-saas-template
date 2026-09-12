# Architecture

## Goals

The architecture optimizes for:

1. fast creation of new agentic SaaS products,
2. streaming agent experiences,
3. secure multi-tenant B2B patterns,
4. clear separation of deterministic and probabilistic code,
5. portable tools through MCP,
6. measurable agent quality,
7. repeatable infrastructure,
8. easy system-design explanation.

## System Context

```text
                         ┌──────────────┐
                         │    User      │
                         └──────┬───────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ Next.js + CopilotKit  │
                   │ WorkOS AuthKit        │
                   └───────┬────────┬──────┘
                           │        │
                  normal   │        │ agent
                  requests │        │ interactions
                           ▼        ▼
         ┌─────────────────────────────────────────────────┐
         │ services/backend — one process, three packages   │
         │                                                  │
         │  ┌────────────┐              ┌────────────────┐  │
         │  │ FastAPI    │              │ Agent  /agent  │  │
         │  │ /plans     │              │ Anthropic SDK  │  │
         │  └─────┬──────┘              └───────┬────────┘  │
         │        │                             │           │
         │        │                             ▼           │
         │        │                     ┌────────────────┐  │
         │        │◄────────────────────│ MCP    /mcp    │  │
         │        │  verified bearer    └────────────────┘  │
         └────────┼──────────────────────────────────────────┘
                  ▼
            ┌────────────┐
            │ Persistence│
            └────────────┘
```

Sharing a process is a deployment decision, not a coupling: the agent reaches
its tools over MCP at a URL, and every hop verifies identity independently.
See [ADR-009](adr/ADR-009-one-backend-deployable.md).

## Responsibility Boundaries

### Next.js

Owns:

- pages and navigation,
- application UI,
- server-side session integration where required,
- CopilotKit runtime integration,
- map and non-MCP application components,
- client interaction state.

Does not own:

- authoritative authorization decisions,
- durable domain data,
- agent orchestration.

### WorkOS

Owns:

- authentication,
- sessions,
- user identities,
- organizations,
- memberships,
- roles and permissions.

Application resources are scoped by organization.

### FastAPI

Owns deterministic domain behavior:

```text
route → service → persistence
```

Examples:

- create/update/save plan,
- load user preferences,
- list saved plans,
- upload documents,
- persist agent run metadata,
- enforce authorization,
- tenant-scoped queries.

FastAPI should remain useful but boring.

### The agent (`/agent`)

Owns execution of nondeterministic agent workloads:

- model interaction,
- reasoning,
- planning,
- tool selection,
- streaming execution,
- agent lifecycle,
- memory/tracing integrations.

It calls Claude through the Anthropic SDK — the Claude API directly, or Bedrock
through the Mantle endpoint. Both are the same code path; the provider changes
cost and setup, not behaviour.

Prefer small tools with narrow contracts rather than a giant `do_everything()` function.

### MCP (`/mcp`)

MCP is the interoperability boundary for capabilities.

Typical flow:

```text
Agent
  ↓
MCP client
  ↓
MCP server  (/mcp on the backend)
  ↓
tool target / API
```

The same endpoint serves any other MCP client — Claude Desktop, VS Code — which
is what the protocol boundary buys. If the tools only ever shipped with this
agent, calling the functions directly would be the honest simplification.

### MCP Apps

Use MCP Apps when a tool naturally returns interactive UI.

Reference demo:

```text
plan_evening()
   ↓
itinerary data
   ↓
MCP App resource
   ↓
interactive map / itinerary rendered in CopilotKit
```

Do not use MCP Apps for every UI component. Normal product UI remains normal Next.js code.

---

# Identity and Authorization

## Identity propagation

Identity travels as the WorkOS **access token** — a signed JWT — and every hop
verifies it independently rather than trusting the hop before it.

```text
Browser                    (holds a session cookie; never a bearer token)
  ↓
Next.js server             verifies the WorkOS session
  ↓  Authorization: Bearer <jwt>
Agent runtime              forwards the assertion unchanged
  ↓  Authorization: Bearer <jwt>
MCP server                 forwards the assertion unchanged
  ↓  Authorization: Bearer <jwt>
FastAPI                    verifies the signature against WorkOS JWKS,
                           derives user_id / organization_id / permissions,
                           and authorizes
```

Two properties fall out of this shape:

- **No hop can forge a tenant.** The API derives `organization_id` from a
  signature it verified, not from anything a caller sent.
- **The agent holds no credential of its own.** It acts strictly on behalf of
  the authenticated user, so it can never exceed that user's access.

The browser never holds the token. It is attached server-side, in the CopilotKit
runtime route (`apps/web/src/app/api/copilotkit/[[...path]]/route.ts`), which is
the identity injection boundary.

Never allow the LLM to invent or override `organization_id`, `user_id`, or
permission claims. In this implementation it structurally cannot: the create and
update schemas have no such fields, so an invented value is dropped at
validation.

## Enforcement

Permission checks occur at execution boundaries.

```text
Agent proposes tool
       ↓
Tool validates context
       ↓
Service validates permission + tenant
       ↓
Persistence executes scoped operation
```

A human approval is not authorization.

```text
approved == true
```

does not imply:

```text
authorized == true
```

---

# Data Model

Minimal reference entities:

```text
users
organizations
projects
plans
plan_stops
agent_runs
agent_tool_calls
user_preferences
```

Every organization-owned entity includes:

```text
organization_id
```

Example `plans`:

```text
id
organization_id
created_by_user_id
name
status
start_at
budget
created_at
updated_at
```

Example `agent_runs`:

```text
id
organization_id
user_id
agent_name
model
status
started_at
completed_at
latency_ms
input_tokens
output_tokens
estimated_cost
trace_id
```

---

# Streaming Architecture

Do not force the deterministic API routes to proxy model output. Sharing a
process does not change this: the agent has its own mount and its own streaming
path.

Preferred path:

```text
Claude (Claude API or Bedrock)
   ↓
agent_app  (/agent, SSE)
   ↓
CopilotKit / AG-UI
   ↓
Browser
```

Stream semantic events in addition to text deltas:

```text
RUN_STARTED
TOOL_CALL_START
TOOL_CALL_END
STATE_DELTA
TEXT_MESSAGE_CONTENT
APPROVAL_REQUESTED
RUN_FINISHED
RUN_ERROR
```

The exact event vocabulary should align with the framework/protocol rather than duplicating an unnecessary custom event standard.

---

# Failure Model

Agent systems should explicitly handle:

- model timeout,
- tool timeout,
- malformed tool arguments,
- tool authorization failure,
- third-party API throttling,
- zero search results,
- partial search results,
- stale data,
- disconnected stream,
- user cancellation,
- duplicate retries,
- persistence failure.

Prefer idempotency keys for externally consequential actions.

Example:

```text
tool_call_id → idempotency_key
```

---

# Observability

Correlate:

```text
request_id
run_id
trace_id
user_id
organization_id
tool_call_id
```

Capture:

- model,
- latency,
- tokens,
- cost estimate,
- tool calls,
- tool errors,
- authorization failures,
- retries,
- final result,
- evaluator scores.

Never put secrets or unnecessarily sensitive user data into logs.

---

# Scalability

The starter intentionally avoids premature scale complexity.

Stateless layers:

- Next.js application instances,
- the application API,
- the agent's streaming endpoint,
- MCP service replicas.

Durable state:

- Postgres,
- S3,
- optional DynamoDB,
- durable agent memory where appropriate.

Scale each independently.

---

# Local vs Cloud

```text
LOCAL
Next.js          → local process/container
FastAPI          → local process/container
Postgres         → Docker
AWS primitives   → LocalStack where useful
Agent            → agentcore dev
MCP              → local process/container

CLOUD
Next.js              → Vercel
Backend (all three)  → one container: Fly, Render, Cloud Run, ECS
Postgres             → Neon, RDS/Aurora, or any managed Postgres
S3                   → AWS S3

The AWS path — Lambda, AgentCore, RDS in a VPC — is preserved under
advanced/ for when the split earns its cost.
```

Local development should preserve contracts, not perfectly reproduce managed infrastructure internals.

---

# Reference Demo Flow

```text
"Plan my evening near me"
          ↓
validate session
          ↓
resolve location with user consent
          ↓
agent creates plan
          ↓
search places/events tools
          ↓
route/rank candidates
          ↓
stream progress
          ↓
render itinerary + map
          ↓
user: "make it cheaper"
          ↓
agent replans
          ↓
user: "save it"
          ↓
permission check
          ↓
FastAPI service
          ↓
Postgres
```

This one workflow exercises most of the template without requiring a large product surface.
