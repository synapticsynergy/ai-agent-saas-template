# ai-agent-saas-template

A reusable, production-oriented starter for building full-stack agentic SaaS applications.

The template is intentionally opinionated around:

- **Next.js + TypeScript** for the product UI
- **CopilotKit / AG-UI** for agent ↔ UI interaction and streaming
- **WorkOS AuthKit** for authentication, organizations, and RBAC
- **FastAPI + Python** for deterministic application APIs and persistence
- **Amazon Bedrock AgentCore Runtime** for agent execution
- **Strands Agents** for Python agent orchestration
- **MCP / AgentCore Gateway** for tools and interoperable agent capabilities
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
│   └── web/                     # Next.js + CopilotKit + WorkOS
├── services/
│   ├── api/                     # FastAPI application API
│   ├── agent/                   # Strands agent for AgentCore Runtime
│   └── mcp/                     # Custom MCP server / MCP Apps
├── packages/
│   └── contracts/               # Shared generated schemas/types
├── infra/
│   └── terraform/
│       ├── modules/
│       └── envs/
│           ├── dev/
│           ├── staging/
│           └── prod/
├── evals/
├── tests/
├── docs/
├── docker-compose.yml
├── Makefile
└── README.md
```

Recommended application structure:

```text
services/api/
├── app/
│   ├── auth/
│   ├── routes/
│   ├── services/
│   ├── persistence/
│   ├── models/
│   ├── schemas/
│   └── main.py
└── tests/

services/agent/
├── agent.py
├── prompts/
├── workflows/
├── tools/
└── tests/

services/mcp/
├── server.py
├── tools/
├── resources/
└── tests/
```

---

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

Install:

- Git
- Docker Desktop / Docker Engine
- Node.js
- pnpm
- Python 3.12+
- uv
- Terraform
- AWS CLI
- AgentCore CLI
- LocalStack CLI (`lstk`)
- Make

### Clone

```bash
git clone <repo-url>
cd ai-agent-saas-template
cp .env.example .env
```

### Install dependencies

```bash
make install
```

Equivalent:

```bash
pnpm --dir apps/web install
uv sync --project services/api
uv sync --project services/agent
uv sync --project services/mcp
```

### Start local dependencies

```bash
make infra-up
```

### Start the application

```bash
make dev
```

For services in separate terminals:

```bash
make web-dev
make api-dev
make agent-dev
make mcp-dev
```

### Run tests

```bash
make test
```

### Run agent evaluations

```bash
make eval
```

### Validate Terraform

```bash
make infra-check
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

## Architecture Review Story

The shortest explanation of the architecture:

> I separated deterministic SaaS workloads from nondeterministic agent workloads. Next.js and CopilotKit provide the interactive agent UI, WorkOS handles B2B identity and permissions, FastAPI/Lambda handles normal application services and persistence, and AgentCore hosts the agent runtime. The agent accesses capabilities through MCP and AgentCore Gateway. Identity and tenant context propagate into the agent workflow, but authorization is revalidated at deterministic tool and service boundaries. Agent execution streams typed events to the UI and is covered by traces, evaluations, integration tests, and IaC.

See [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md).

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

---

## MVP Definition

### SaaS

- [ ] Next.js UI
- [ ] WorkOS authentication
- [ ] organizations + memberships
- [ ] permission-based RBAC
- [ ] tenant isolation
- [ ] FastAPI API
- [ ] persistence
- [ ] S3 storage

### Agent

- [ ] AgentCore-hosted Strands agent
- [ ] Bedrock model
- [ ] streaming
- [ ] CopilotKit / AG-UI
- [ ] shared UI/agent state
- [ ] MCP tool use
- [ ] MCP App / interactive map
- [ ] human approval
- [ ] memory
- [ ] traces
- [ ] evaluations

### Engineering

- [ ] Docker local development
- [ ] LocalStack for applicable AWS dependencies
- [ ] Terraform
- [ ] dev/staging/prod environments
- [ ] CI/CD
- [ ] unit tests
- [ ] integration tests
- [ ] E2E tests

---

## Goal

This is **not a chatbot starter**.

It is a reusable foundation for building agentic products where AI participates in real workflows while the surrounding application remains secure, testable, observable, deployable, and easy to explain.
