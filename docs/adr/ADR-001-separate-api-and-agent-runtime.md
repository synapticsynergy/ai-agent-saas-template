# ADR-001: Separate the Application API and Agent Runtime

**Status:** Accepted

## Context

A full-stack agentic SaaS application needs both conventional deterministic APIs and nondeterministic agent execution.

The two workloads have different requirements.

Application APIs favor:

- short predictable requests,
- deterministic authorization,
- CRUD,
- transactional persistence.

Agent workloads favor:

- streaming,
- longer execution,
- model/tool loops,
- memory,
- agent-specific traces/evaluations.

## Decision

Run deterministic application APIs in FastAPI/Lambda and agent execution in AgentCore Runtime.

The normal FastAPI service does not proxy the agent stream by default.

## Consequences

Positive:

- independent scaling,
- clearer ownership,
- simpler streaming path,
- better failure isolation,
- easier architectural explanation.

Negative:

- more deployable components,
- identity context must cross boundaries,
- observability needs correlation IDs.
