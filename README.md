# ai-agent-saas-template

A reusable, production-oriented starter for building full-stack agentic SaaS applications.

The template is intentionally opinionated around:

- **Next.js + TypeScript + Material UI** for the product UI
- **CopilotKit / AG-UI** for agent ↔ UI interaction and streaming
- **WorkOS AuthKit** for authentication, organizations, and RBAC
- **FastAPI + Python** for deterministic application APIs and persistence
- **Amazon Bedrock AgentCore Runtime** for agent execution
- **Strands Agents** for Python agent orchestration
- **MCP / AgentCore Gateway** for tools and interoperable agent capabilities
- **Leaflet + OpenStreetMap** for the itinerary map
- **Postgres, S3, and optional DynamoDB** for application persistence
- **Terraform** for AWS infrastructure as code
- **Docker Compose + LocalStack** for fast local development of conventional AWS services
- **AgentCore CLI** for local agent development and deployment
- **GitHub Actions** for CI/CD

The project is designed to make new AI-agent SaaS applications quick to bootstrap while keeping architectural decisions explicit, testable, and understandable to contributors.

---

## Reference Application: "Plan My Evening"

The starter includes a deliberately small reference application:

> "Plan my evening near me. I want dinner, live music, and drinks. Keep it walkable and under $100."

The agent:

1. receives authenticated user and organization context,
2. discovers nearby places and live events,
3. reasons about time, distance, budget, and preferences,
4. streams progress and tool execution to the UI,
5. renders a map + itinerary,
6. supports conversational replanning,
7. asks for approval when appropriate,
8. persists a saved plan.

Example follow-ups:

- "Make it cheaper."
- "Replace the show with jazz."
- "Turn this into a 4-stop bar crawl."
- "Make a scavenger hunt for four friends."
- "Save this plan."

The point is not to build a nightlife platform. The point is to exercise the reusable agentic SaaS architecture with one instantly understandable workflow.

---

## Architecture

```text
                                 ┌────────────────────────────────┐
                                 │            Browser             │
                                 │                                │
                                 │ Next.js + CopilotKit / AG-UI  │
                                 │ WorkOS AuthKit                 │
                                 └───────────────┬────────────────┘
                                                 │
                                  authenticated identity context
                                                 │
                        ┌────────────────────────┴───────────────────────┐
                        │                                                │
                        ▼                                                ▼
             ┌──────────────────────┐                        ┌──────────────────────┐
             │ Deterministic API    │                        │ Agent Runtime        │
             │                      │                        │                      │
             │ API Gateway          │                        │ AgentCore Runtime    │
             │ FastAPI on Lambda    │                        │ Strands Agent        │
             └──────────┬───────────┘                        └──────────┬───────────┘
                        │                                               │
                        │                                               │ MCP
                        ▼                                               ▼
             ┌──────────────────────┐                        ┌──────────────────────┐
             │ Application Data    │                        │ Tool Layer           │
             │                      │                        │                      │
             │ Postgres            │◄───────────────────────│ AgentCore Gateway    │
             │ S3                  │                        │ MCP Servers          │
             │ DynamoDB (optional) │                        │ External APIs        │
             └──────────────────────┘                        └──────────────────────┘
```

### Core design rule

**Deterministic application workloads and nondeterministic agent workloads are separate.**

FastAPI owns things that should behave predictably:

- CRUD
- persistence
- tenant scoping
- authorization
- file operations
- business rules
- deterministic integrations

AgentCore owns things that are naturally agentic:

- model inference
- reasoning loops
- tool selection
- long-running agent execution
- streaming agent events
- memory
- traces and evaluations

The LLM is never the security boundary.

---

## Repository Layout

```text
ai-agent-saas-template/
├── apps/
│   └── web/                     # Next.js + MUI + CopilotKit + WorkOS
├── services/
│   ├── api/                     # FastAPI application API
│   ├── agent/                   # Strands agent for AgentCore Runtime
│   └── mcp/                     # MCP server and MCP App resource
├── packages/
│   └── contracts/               # Shared domain contracts + generated types
├── infra/
│   └── terraform/
│       ├── modules/             # networking, database, storage, api, mcp, observability
│       └── envs/                # local, dev, staging, prod — separate state each
├── evals/                       # agent evaluation dataset and runner
├── tests/
│   ├── integration/             # against real Postgres, LocalStack, MCP
│   └── e2e/                     # Playwright
├── scripts/                     # dev, deploy and validation scripts
├── docs/
├── docker-compose.yml
├── Makefile
└── README.md
```

### Where things live

```text
services/api/app/
├── auth/          workos.py (JWT verification), permissions.py, dependencies.py
├── routes/        thin HTTP layer; maps to services
├── services/      authorization + tenant scoping live here
├── persistence/   postgres.py, s3.py, dynamo.py
├── models/        SQLAlchemy
├── schemas/       re-exported from packages/contracts
└── main.py

services/agent/
├── agent.py                 AgentCore contract: /invocations, /ping
├── agent_app/
│   ├── runner.py            orchestration; emits AG-UI events
│   ├── streaming.py         AG-UI event construction
│   ├── workflows/           deterministic planning (see ADR-007)
│   ├── tools/mcp_client.py  MCP client; forwards the caller's token
│   └── prompts/
└── tests/

services/mcp/
├── server.py                entry point
└── mcp_server/
    ├── server.py            tool and MCP App registration
    ├── tools/               narrow, typed, individually testable
    ├── providers/           replaceable adapters; registry selects
    ├── resources/           the ui:// MCP App document
    └── context.py           caller identity extraction
```

### The shared contract

`packages/contracts` holds one definition of the itinerary, plan, tool and
agent-run shapes. The API, the agent and the MCP server import it as a Python
path dependency; `make contracts` generates the JSON Schema and TypeScript the
web app compiles against. CI fails if the generated output is stale.

It also holds the deterministic fixture dataset, so the MCP server's tools and
the agent's eval suite read the same one and cannot drift apart.

This used to be forced: the Strands SDK pinned `mcp<2.2` while the MCP server
needed `mcp>=2.2`, so the two could not share a virtualenv at all. Dropping
Strands for the Anthropic SDK removed that constraint (ADR-009). The dataset
stays here because one definition is still the right shape, not because
anything prevents sharing now.

## Authentication and Tenant Model

Use WorkOS AuthKit for:

- login/logout/session management
- organizations
- organization memberships
- roles
- permissions
- enterprise SSO readiness
- Directory Sync readiness

Every tenant-owned record contains an `organization_id`.

```text
User
  ↓
WorkOS Membership
  ↓
Organization
  ↓
Role(s)
  ↓
Permissions
```

Prefer permission checks:

```python
require_permission("plans:write")
```

over role checks:

```python
if role == "admin":
    ...
```

The model may decide to request a tool call, but deterministic code verifies whether the authenticated user may execute it.

---

## Request Paths

### Standard application API

```text
Browser
  ↓
Next.js
  ↓
API Gateway
  ↓
FastAPI / Lambda
  ↓
Service Layer
  ↓
Persistence
  ↓
Postgres / S3 / DynamoDB
```

### Agent interaction

```text
Browser
  ↓
CopilotKit / AG-UI
  ↓
AgentCore Runtime
  ↓
Strands Agent
  ↓
MCP / AgentCore Gateway
  ↓
Tools / APIs / application services
```

The FastAPI service does not need to proxy the agent stream.

---

## Streaming

Streaming is a first-class feature.

Stream events such as:

```json
{"type":"agent_started"}
{"type":"tool_started","tool":"search_events"}
{"type":"tool_result","tool":"search_events","count":17}
{"type":"state_update","field":"itinerary","value":[]}
{"type":"message_delta","content":"I found three strong options..."}
{"type":"approval_required","action":"save_plan"}
{"type":"agent_finished"}
```

This lets the UI show useful live state:

```text
Planning your evening...

✓ Loaded preferences
✓ Found 17 live events
✓ Found 26 nearby venues
● Optimizing route
○ Building itinerary
```

---

## Local Development Philosophy

Use the fastest local substitute for each layer:

| Layer | Local mode |
|---|---|
| Next.js | native `pnpm dev` or Docker |
| FastAPI | native `uv run fastapi dev` or Docker |
| Postgres | Docker |
| S3 / DynamoDB / Lambda / API Gateway | LocalStack where useful |
| Agent | `agentcore dev` |
| MCP server | native Python or Docker |
| WorkOS | WorkOS development environment |
| External location/event APIs | real sandbox/dev credentials or deterministic test fixtures |

Do **not** force LocalStack to emulate services it is not intended to reproduce. The purpose is fast feedback, not perfect local imitation of every managed AWS feature.

---

## Environment Strategy

Three long-lived environments:

```text
dev       → shared development environment
staging   → release candidate / demo environment
prod      → production
```

Recommended Git branches:

```text
main        → production
staging     → staging
dev         → shared development
feature/*   → new work
bugfix/*    → fixes
```

See [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md).

---

## Quick Start

### Prerequisites

| Tool | Why | Required |
|---|---|---|
| Docker | Postgres and LocalStack | yes |
| Node 20.9+ and pnpm | the web app | yes |
| Python 3.12+ and [uv](https://docs.astral.sh/uv/) | the API, agent and MCP server | yes |
| Make | the developer interface | yes |
| Terraform | infrastructure | to deploy |
| AWS CLI | deployment | to deploy |
| [AgentCore CLI](https://pypi.org/project/bedrock-agentcore-starter-toolkit/) | AgentCore Runtime parity | optional locally |

`pnpm` comes with Node: `corepack enable pnpm`.

### Run it

```bash
git clone <repo-url>
cd ai-agent-saas-template

cp .env.example .env
make install
make infra-up
make dev
```

Then open <http://localhost:3000>, go to the planner, and open the assistant in
the corner. The map fills the page and the itinerary floats over it as the agent
builds it.

Out of the box this runs **without any cloud credentials**:

- `AUTH_DEV_FIXTURE=1` supplies a deterministic local identity in place of
  WorkOS. It is refused outside `APP_ENV=local` by both the web app and the API.
- `AGENT_MODEL_PROVIDER=scripted` skips Bedrock inference and parses requests
  with rules. Only request interpretation is affected — the planner, the tools
  and the whole authorization path are the real ones
  ([ADR-007](docs/adr/ADR-007-deterministic-planner.md)).
- `PLACES_PROVIDER=fixture` serves a deterministic local dataset instead of a
  third-party API.

To use the real services, set `WORKOS_*`, `AGENT_MODEL_PROVIDER=bedrock` and the
provider credentials in `.env`. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

`make dev` runs all four in one terminal; **Ctrl-C stops them all**. If a server
is ever left holding a port, `make dev-stop` reclaims them.

### Individual services

```bash
make web-dev       # http://localhost:3000
make backend-dev   # http://localhost:8000
```

The backend serves all three surfaces from one process (ADR-009):

```text
http://localhost:8000/health        the application API
http://localhost:8000/agent/ping    the agent
http://localhost:8000/mcp           the MCP server
```

### Tests

```bash
make check              # fast pre-push suite
make test-unit          # unit, service and tool-contract tests
make test-integration   # against real Postgres, LocalStack and MCP
make test-e2e           # Playwright, against the running stack
make eval               # agent evaluations
make test               # everything
```

### Infrastructure

```bash
make infra-check              # terraform fmt + validate
make terraform-plan ENV=dev
make deploy-dev
```

---

## Deployment

### Development

```bash
git checkout dev
git pull
make test
make deploy-dev
```

### Staging

```bash
git checkout staging
git merge dev
git push origin staging
make deploy-staging
```

### Production

```bash
git checkout main
git merge staging
git push origin main
make deploy-prod
```

For normal team use, deployments should be triggered by CI after branch protection and required checks rather than by developers manually running production deploy commands.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Testing Pyramid

```text
                 E2E
              Integration
            Agent Evals
          Tool Contract Tests
        Service / Auth Tests
             Unit Tests
```

Traditional business logic should be deterministic.

Agent behavior should be evaluated with scenarios and objective evaluators rather than brittle exact-string assertions.

Security-sensitive agent behavior should have deterministic tests:

```text
Given:
viewer permission set

When:
agent requests save_plan()

Expected:
tool/service denies execution
```

See [docs/TESTING.md](docs/TESTING.md).

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Design Principles](docs/DESIGN_PRINCIPLES.md)
- [Development](docs/DEVELOPMENT.md)
- [Git Workflow](docs/GIT_WORKFLOW.md)
- [Testing](docs/TESTING.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Reference Application](docs/REFERENCE_APP.md)
- [Template Checklist](docs/TEMPLATE_CHECKLIST.md)
- [Architecture Decision Records](docs/adr/)

### Decisions

- [ADR-001 — Separate the API and agent runtime](docs/adr/ADR-001-separate-api-and-agent-runtime.md) *(superseded by ADR-009)*
- [ADR-002 — WorkOS for B2B auth and RBAC](docs/adr/ADR-002-workos-for-b2b-auth.md)
- [ADR-003 — MCP for reusable agent capabilities](docs/adr/ADR-003-mcp-for-agent-tools.md)
- [ADR-004 — LocalStack, used selectively](docs/adr/ADR-004-localstack-scope.md)
- [ADR-005 — The agent emits AG-UI directly](docs/adr/ADR-005-agui-emitted-by-the-agent.md)
- [ADR-006 — AgentCore resources are not managed by Terraform](docs/adr/ADR-006-agentcore-owns-its-own-resources.md) *(superseded by ADR-009)*
- [ADR-007 — The planner is deterministic](docs/adr/ADR-007-deterministic-planner.md)
- [ADR-008 — Conversation threads are not stored](docs/adr/ADR-008-conversation-threads-are-not-stored.md)
- [ADR-009 — One backend deployable](docs/adr/ADR-009-one-backend-deployable.md)

### Service guides

- [Web application](apps/web/README.md)
- [Application API](services/api/README.md)
- [Agent](services/agent/README.md)
- [MCP server](services/mcp/README.md)

---

## What the Template Implements

### SaaS

- [x] Next.js UI with Material UI as the single design system
- [x] WorkOS AuthKit authentication, with an isolated local fixture identity
- [x] Organizations and permission-based RBAC
- [x] Tenant isolation enforced in the service layer and covered by tests
- [x] FastAPI application API on Lambda
- [x] Postgres persistence with Alembic migrations
- [x] S3 object storage with tenant-prefixed keys
- [ ] Directory Sync / enterprise SSO (WorkOS supports it; not wired up here)

### Agent

- [x] Strands agent serving the AgentCore Runtime contract
- [x] Streaming AG-UI events: run lifecycle, steps, tools, state, approvals
- [x] CopilotKit runtime with server-side identity injection
- [x] Shared UI/agent state — the itinerary is application state, not prose
- [x] MCP tool use over streamable HTTP
- [x] MCP App resource (`ui://itinerary/map`), with a Leaflet fallback in the
      web app (see [REFERENCE_APP.md](docs/REFERENCE_APP.md#mcp-app) for what
      the host does not yet support)
- [x] Human approval, kept distinct from authorization
- [x] Agent run and tool-call records for traces and cost
- [x] Evaluation suite scoring structured outcomes
- [ ] AgentCore Memory (the agent is stateless across runs by design; see
      [ADR-008](docs/adr/ADR-008-conversation-threads-are-not-stored.md))

### Engineering

- [x] Docker Compose local development
- [x] LocalStack for the AWS services it reproduces well
- [x] Terraform for local, dev, staging and prod, with isolated state
- [x] GitHub Actions CI/CD with OIDC, no static AWS credentials
- [x] Unit, service, tool-contract, integration and end-to-end tests
- [x] Agent evaluations gating promotion

## Goal

This is **not a chatbot starter**.

It is a reusable foundation for building agentic products where AI participates in real workflows while the surrounding application remains secure, testable, observable, deployable, and easy to explain.
