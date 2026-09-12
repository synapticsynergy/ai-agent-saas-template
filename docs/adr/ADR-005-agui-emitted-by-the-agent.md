# ADR-005: The Agent Emits AG-UI Directly

**Status:** Accepted

## Context

The agent has to stream more than token deltas: tool lifecycle, progress steps,
structured state updates and approval requests all need to reach the browser
while a run is in flight.

There were three plausible places to define that vocabulary:

1. a custom event protocol invented for this template,
2. AG-UI events emitted by the agent itself,
3. a translation layer that converts internal events into whatever the UI wants.

The architecture documentation already warns against the first: "The exact event
vocabulary should align with the framework/protocol rather than duplicating an
unnecessary custom event standard."

## Decision

The agent emits AG-UI events directly, as Server-Sent Events, from its
`POST /invocations` endpoint — reachable at `/agent/invocations` since the agent
became a mount on the backend (ADR-009). CopilotKit consumes them without
translation.

Application-level names that ride inside those events — progress stage names,
the `approval_requested` custom event — are defined once in
`packages/contracts/src/saas_contracts/streaming.py` and consumed by both the
agent and the web app.

This originally had to compose with the AgentCore Runtime contract, which
required `POST /invocations` and `GET /ping` and was agnostic about the response
body. AgentCore is gone (ADR-009), but the endpoint names stayed: they cost
nothing, and keeping them means the agent can be lifted back onto a runtime that
expects that contract without touching the streaming code.

## Consequences

Positive:

- no parallel protocol to keep in sync,
- CopilotKit's client-side state handling works out of the box,
- the event stream is inspectable with `curl`,
- swapping the UI framework does not require changing the agent.

Negative:

- the agent is coupled to AG-UI's event shapes,
- AG-UI is pre-1.0 and its types may move,
- SSE framing has to be exactly right. The AG-UI client splits frames on `\n\n`,
  so the agent must emit LF separators; `sse-starlette` defaults to CRLF, which
  produces a stream that never parses. This is configured explicitly in
  `services/backend/agent_app/asgi.py` and is the kind of detail that only surfaces
  end-to-end, which is why the E2E suite exercises the real stream.
