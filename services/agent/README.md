# Agent service

A Strands-based agent for Amazon Bedrock AgentCore Runtime, serving the
reference "Plan My Evening" workflow.

## What runs where

| Concern | Where it lives | Why |
|---|---|---|
| Interpreting the request | `interpreter.py` — Strands on Bedrock | Language understanding is what a model is for. |
| Choosing venues, timing, budget | `workflows/planner.py` | Deterministic, testable, auditable. |
| Reaching tools | `tools/mcp_client.py` over MCP | Portable capability boundary (ADR-003). |
| Deciding if a write is allowed | the application API | The model is not a security boundary. |

## The model's job

Exactly one thing: turn a sentence into a `PlanningRequest`. It is asked for
structured output, so a malformed answer fails at the schema boundary rather
than becoming a strange itinerary.

Two things it is deliberately not allowed to decide, and which are re-pinned
after every call whatever it returns:

- **where the user is** — that comes from the browser,
- **what time it is** — that comes from the server.

A model failure degrades to rule-based extraction rather than failing the run,
so a Bedrock outage costs understanding, not availability.

The planner is deliberately model-free. That is not a limitation — it is the
template's central principle applied to the agent itself: keep the
nondeterministic surface small, and everything you would want to test, audit or
explain stays ordinary code.

## Local development

```bash
make agent-dev
```

Uses the AgentCore CLI when it is installed (`uv tool install
bedrock-agentcore-starter-toolkit`), which reproduces the AgentCore Runtime
contract. Falls back to uvicorn otherwise, serving the identical app.

Without AWS credentials, set `AGENT_MODEL_PROVIDER=scripted`. Interpretation
then uses rule-based extraction; everything else — the planner, the tools, the
streaming and the whole authorization path — is unchanged. Refused outside
`APP_ENV=local`.

## Choosing a model

`AGENT_MODEL_PROVIDER` picks what interprets requests and writes replies:

| Provider | Needs | Notes |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` (or `ant auth login`) | Least setup. Default model `claude-opus-5`; set `ANTHROPIC_MODEL_ID` to `claude-sonnet-5` or `claude-haiku-4-5` to spend less. |
| `bedrock` | AWS credentials, plus model access granted in the Bedrock console | Keeps inference inside your AWS account. Pricing is set by AWS. |
| `scripted` | nothing | No model call. Local and test only. |

The model does two short jobs per run — turning a sentence into constraints,
and a two- or three-sentence reply — so cost is dominated by which model you
choose rather than which platform serves it. Everything else (planner, tools,
streaming, authorization) is identical across providers.

## HTTP contract

| Route | Purpose |
|---|---|
| `POST /invocations` | Run the agent. Accepts AG-UI `RunAgentInput`, returns an AG-UI SSE stream. |
| `POST /` | Same handler, so CopilotKit's `HttpAgent` can point here directly. |
| `GET /ping`, `GET /health` | Health probe. |

## Identity

The caller's WorkOS access token arrives as `Authorization: Bearer <jwt>` and is
forwarded unchanged to the MCP tool layer, which forwards it to the application
API. The agent holds no credential of its own for tenant operations.

## Evaluations

```bash
make eval
```

See `evals/` at the repository root.
