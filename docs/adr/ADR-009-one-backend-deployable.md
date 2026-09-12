# ADR-009: One Backend Deployable

**Status:** Accepted — supersedes [ADR-001](ADR-001-separate-api-and-agent-runtime.md)

## Context

ADR-001 separated the deterministic application API (FastAPI on Lambda) from
agent execution (Strands on AgentCore Runtime). ADR-003 then put agent tools
behind MCP in a third service. The reasoning still holds on its own terms: the
two workloads genuinely have different shapes, and independent scaling and
failure isolation are real benefits.

What changed is the goal. This repository is a template meant to be cloned and
deployed quickly. Against that goal the split had costs ADR-001 listed as
acceptable and which turned out not to be:

- Four deployables, four virtualenvs and four Dockerfiles before a single line
  of product code.
- Terraform across four environments as the only path to a running system.
- A dependency conflict that separate virtualenvs had hidden: the MCP Apps UI
  resource needs `mcp>=2.2`, and `strands-agents` caps it below that. Nothing
  reported this until the packages had to resolve together.
- No deployment story at all for the web app — `scripts/deploy/web.sh` refused
  to run until a host was configured, so the template could not actually be
  deployed by someone cloning it.

The benefits, meanwhile, are worth what they cost at a scale this template does
not start at. A template should make the first deploy cheap and the split
available later, not the reverse.

## Decision

Run the application API, the agent and the MCP server as one ASGI application,
composed in `services/backend/asgi.py` and mounted at `/`, `/agent` and `/mcp`.

They remain three independent Python packages — `app`, `agent_app` and
`mcp_server`. None imports another except through HTTP or the shared contracts
package, and the agent still reaches its tools over MCP at a URL rather than by
calling the tool functions directly. Splitting them back into separate
deployables is therefore a configuration change: point `MCP_SERVER_URL` and
`AGENT_BASE_URL` elsewhere and deploy the same image three times.

Drop Lambda and AgentCore Runtime. The agent streams SSE, which wants a
long-lived connection rather than an invocation; Mangum behind API Gateway was
always a poor fit for it. Any host that runs a container works instead.

## Consequences

Positive:

- One `uv sync`, one image, one deploy.
- The agent's SSE path stops fighting its host.
- The MCP server gets a stable public URL, which is what makes it reachable
  from Claude Desktop and other MCP clients — the thing that justifies the
  protocol boundary at all.
- Dependency conflicts between the three surface at resolution time rather than
  in production.

Negative:

- No independent scaling. A burst of agent traffic shares a process with CRUD
  requests. At the scale this template starts at, that is not a constraint; at
  the scale where it is, the split above is available.
- No failure isolation. A crash takes all three down. Mitigated by the fact
  that none of the three can corrupt another's state — authorization is still
  enforced independently on every request, including from inside this process.
- One dependency set. The upper bound any of the three needs is now the upper
  bound for all of them.

## What did not change

The security model. ADR-001 argued that the LLM is never the security boundary,
and sharing a process does not soften that: `save_plan` still forwards the
caller's bearer assertion to the API, which verifies the signature and checks
the permission. The service layer re-checks independently of any route
decorator, so a caller arriving in-process has no more authority than one
arriving over the network.
