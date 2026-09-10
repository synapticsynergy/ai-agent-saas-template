# Design Principles

These principles guide additions to the template.

## Separate deterministic and nondeterministic workloads

Transactional application behavior belongs in conventional application services.

Agent execution belongs in the agent runtime.

## The model is not a security boundary

The model may propose actions.

Authentication, authorization, tenant isolation, validation, and side-effect controls are enforced by deterministic code.

## Prefer narrow tools

Tools should expose focused capabilities with typed inputs and outputs.

Prefer:

```text
search_events
get_place
save_plan
```

over:

```text
manage_everything
```

## Use MCP where interoperability earns its complexity

MCP is useful for reusable, independently deployable, discoverable capabilities and interactive MCP Apps.

Not every internal function needs to become an MCP service.

## Stream state, not only prose

The application should be able to render tool progress, structured state changes, approvals, errors, and text while an agent is running.

## Keep application state separate from agent memory

Business records belong in application persistence.

Agent memory exists to improve future agent interactions.

Conversation history is not the application database.

## Authorization and approval are different

Human approval expresses intent.

Authorization determines whether the authenticated principal may execute the action.

Both may be required.

## Optimize local development for feedback speed

Use local containers and emulators where they provide useful contract fidelity.

Use supported cloud-service development tooling when emulation would create false parity.

## Infrastructure should be reproducible

Cloud resources and environment differences should be represented as code wherever practical.

Avoid undocumented console-only configuration.

## Agent quality is measurable

Prompts, models, tools, and orchestration can regress.

Maintain evaluation datasets and track behavioral, latency, cost, and security metrics over time.

## Prefer replaceable adapters

Provider-specific SDKs should remain near integration boundaries.

Domain services and tool contracts should not become unnecessarily coupled to a single vendor.
