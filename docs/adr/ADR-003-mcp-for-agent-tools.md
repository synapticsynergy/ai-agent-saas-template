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

## Note after ADR-009

"Independent deployment" is still one of the criteria above, but it is no longer
a property this template exercises: the MCP server shares a process with the
agent that calls it. The agent still reaches it over HTTP at `MCP_SERVER_URL`,
so nothing about the boundary is faked — but the cost above is being paid for
**interoperability** alone.

That is a real payoff and worth being explicit about: the same `/mcp` endpoint
serves Claude Desktop, VS Code, or any other MCP host, with no extra code. If a
downstream product never wants that, calling the tool functions directly is the
honest simplification, and the decision above says as much.
