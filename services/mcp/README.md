# MCP server

Agent-facing capabilities over MCP, served on streamable HTTP.

## What belongs here

Capabilities that earn a protocol boundary: reusable, independently deployable,
useful to more than one agent
([ADR-003](../../docs/adr/ADR-003-mcp-for-agent-tools.md)). Internal helpers —
scoring, geometry, formatting — stay ordinary Python.

| Tool | Consequential | Identity required |
|---|---|---|
| `search_places` | no | no |
| `search_events` | no | no |
| `get_place_details` | no | no |
| `build_route` | no | no |
| `save_plan` | **yes** | **yes** |
| `render_itinerary` | no | no |

Tool signatures are flat rather than taking a nested payload object: a model
picks arguments far more reliably from a flat schema, and the typed contracts in
`saas_contracts.tools` still do the validating.

## This server is not a security boundary

`save_plan` extracts the caller's bearer assertion and forwards it to the
application API, which verifies the signature and checks `plans:write`. The MCP
server makes no authorization decision of its own, so there is exactly one place
that can be wrong.

It holds no credential of its own either — which is why its IAM role in
Terraform grants almost nothing.

## Providers

Places, events and routing sit behind `Protocol` interfaces with a deterministic
fixture default. The fixture re-anchors its dataset on whatever coordinate is
requested, so it is not tied to any one city. Swap a provider by editing
`providers/registry.py`; nothing else changes.

Every automated test runs against the fixtures, so results are exact and no test
depends on a third party.

## MCP App

`ui://itinerary/map` is a `text/html;profile=mcp-app` resource bound to
`render_itinerary`. See [REFERENCE_APP.md](../../docs/REFERENCE_APP.md#mcp-app)
for what host support currently allows.

## Commands

```bash
make mcp-dev
uv run --project services/mcp pytest services/mcp/tests
```
