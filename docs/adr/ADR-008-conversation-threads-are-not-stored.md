# ADR-008: Conversation Threads Are Not Stored

**Status:** Accepted

## Context

The CopilotKit SSE runtime ships an in-memory agent runner that keeps
conversation threads, and exposes them through `/threads` on the runtime
endpoint. It works with no configuration, which is what makes it worth examining
before shipping.

Running the template revealed what it actually does:

```
GET /api/copilotkit/threads?agentId=planner

{"threads":[{"id":"...","organizationId":"","createdById":"", ...}, ...]}
```

The store is process-global. `organizationId` and `createdById` are empty. Any
authenticated caller receives every thread the process has seen, including
other organizations'.

That is a tenant boundary this template exists to hold. It also broke the
end-to-end suite in a revealing way: fresh browser contexts resumed each other's
threads, so tests passed by reading a previous test's itinerary.

## Decision

Block the thread endpoints. `apps/web/src/app/api/copilotkit/[[...path]]/route.ts`
returns 404 for anything under `/threads`.

Nothing in the template needs them:

- the working itinerary travels as AG-UI state, round-tripping between the
  browser and the agent within a run,
- a saved plan is a row in Postgres, scoped by `organization_id` and retrievable
  through the deterministic API with no agent involved,
- agent run metadata — latency, tokens, tool calls, failures — is recorded in
  `agent_runs` and `agent_tool_calls`.

Conversation history is not the application database (docs/DESIGN_PRINCIPLES.md).
The application state that matters is already durable and already tenant-scoped.

## Consequences

Positive:

- no cross-tenant disclosure through the runtime,
- one place owns durable state, and it enforces tenancy,
- the E2E suite became deterministic, and roughly three times faster.

Negative:

- no resumable conversation history across page loads; a reload starts a fresh
  thread with the itinerary carried in client state,
- a downstream product that wants durable conversations has work to do.

## If you need durable conversations

Supply the runtime a `runner` backed by real storage that scopes threads by the
authenticated organization, then unblock the paths. Treat threads as
tenant-owned records like any other: `organization_id` on the row, and every
query filtered by it. The blocked list in the route is the single place to
change.
