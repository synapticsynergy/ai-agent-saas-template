# ADR-003: Use MCP for Reusable Agent Capabilities

**Status:** Accepted

## Context

Agent tools can be implemented as framework-specific local functions, but reusable SaaS templates benefit from a portable tool boundary.

## Decision

Use MCP for capabilities that benefit from interoperability, independent deployment, tool discovery, or MCP Apps.

Do not automatically convert every internal function into MCP.

Internal deterministic helpers may remain normal Python functions/services.

## Consequences

Positive:

- protocol-level interoperability,
- reusable tools,
- language/runtime independence,
- clearer service boundaries,
- supports MCP Apps.

Negative:

- network/protocol overhead,
- additional failure modes,
- more auth/identity propagation complexity.
