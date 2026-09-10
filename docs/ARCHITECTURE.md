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
                 ┌────────────┐   ┌─────────────────┐
                 │ FastAPI    │   │ AgentCore       │
                 │ Lambda     │   │ Runtime         │
                 └─────┬──────┘   └────────┬────────┘
                       │                   │
                       ▼                   ▼
                 ┌────────────┐      ┌──────────────┐
                 │ Persistence│◄─────│ MCP/Gateway  │
                 └────────────┘      └──────────────┘
```

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

### AgentCore Runtime

Owns execution of nondeterministic agent workloads:

- model interaction,
- reasoning,
- planning,
- tool selection,
- streaming execution,
- agent lifecycle,
- memory/tracing integrations.

### Strands Agent

Owns agent behavior and orchestration.

Prefer small tools with narrow contracts rather than a giant `do_everything()` function.

### MCP / AgentCore Gateway

MCP is the interoperability boundary for capabilities.

Typical flow:

```text
Agent
  ↓
MCP client
  ↓
AgentCore Gateway
  ↓
tool target / MCP server / API
```

Gateway provides a consolidated location for tool discovery and invocation.

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

```text
WorkOS session
    ↓
trusted server context
    ├── user_id
    ├── organization_id
    └── permissions
          ↓
     agent request
          ↓
        tools
```

Never allow the LLM to invent or override `organization_id`, `user_id`, or permission claims.

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

Do not force the normal FastAPI Lambda service to proxy model output.

Preferred path:

```text
Bedrock/model
   ↓
Strands
   ↓
AgentCore Runtime
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
- FastAPI Lambda,
- AgentCore Runtime endpoints,
- MCP service replicas.

Durable state:

- Postgres,
- S3,
- optional DynamoDB,
- AgentCore memory where appropriate.

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
Next.js          → selected production hosting
FastAPI          → API Gateway + Lambda
Postgres         → RDS/Aurora or selected managed Postgres
S3               → AWS S3
Agent            → AgentCore Runtime
MCP/Gateway      → AgentCore Gateway / hosted MCP
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
