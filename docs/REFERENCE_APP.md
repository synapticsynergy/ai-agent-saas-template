# Reference Application: Plan My Evening

## Purpose

The reference application provides a small end-to-end implementation of the template architecture.

It is intentionally narrow so each platform capability has a clear purpose.

Primary request:

> Plan my evening near me. I want dinner, live music, and drinks. Keep it walkable and under $100.

The same workflow can support follow-ups such as:

- "Make it cheaper."
- "Replace the show with jazz."
- "Turn this into a four-stop bar crawl."
- "Create a scavenger hunt for four friends."
- "Save this plan."

The goal is not to build a complete nightlife platform. The goal is to provide a concrete reference implementation for authentication, agent execution, streaming, tool use, generative UI, persistence, authorization, observability, and deployment.

---

# User Flow

## 1. Authenticate

The user signs in through WorkOS AuthKit.

The application establishes trusted:

```text
user_id
organization_id
permissions
```

## 2. Request a Plan

```text
Plan my evening near me.
Dinner, live music, then drinks.
Keep it walkable and under $100.
```

## 3. Stream Agent Progress

```text
Planning tonight...

✓ Location confirmed
✓ Found live events
✓ Found nearby restaurants and bars
● Optimizing route
○ Building itinerary
```

The UI receives semantic agent events in addition to text deltas.

## 4. Render Structured Output

```text
7:00 PM  Dinner
          Restaurant A
             ↓ 7 min walk

8:30 PM  Live Music
          Venue B
             ↓ 9 min walk

10:15 PM Drinks
          Bar C

Estimated spend: $84
Walking: 1.3 mi

[ interactive map ]
```

The itinerary is structured application state, not information embedded in
assistant prose.

The implementation makes that literal: the map fills the viewport, the
itinerary floats over it as a header card plus one card per stop, and the
assistant lives in a popup that slides in from the corner. Selecting a card
moves the map; the map's numbered markers select the card. None of it is parsed
out of text — it all comes from the agent's `STATE_SNAPSHOT` events.

## 5. Replan

User:

> Make it cheaper and change the show to jazz.

The agent updates the structured itinerary and map.

## 6. Persist

User:

> Save it.

```text
agent requests save
      ↓
permission check
      ↓
FastAPI plan service
      ↓
Postgres
      ↓
UI confirms saved state
```

---

# Reference Architecture

```text
Next.js / CopilotKit / WorkOS
          │
      ┌───┴─────┐
      ▼         ▼
 FastAPI      Agent  /agent
 /plans       Anthropic SDK
      │         │
      │        MCP
      │         ▼
      │     MCP server  /mcp
      │     tools + ui:// resource
      └──────┬──┘
             ▼
        Persistence
```

---

# Initial Tool Set

Keep the first implementation small:

```text
search_places
search_events
get_place_details
build_route
save_plan
```

Potential later tools:

```text
get_weather
check_reservations
create_calendar_event
share_plan
```

Only add capabilities when they serve a concrete product requirement.

---

# MCP App

`ui://itinerary/map` is a `text/html;profile=mcp-app` resource, registered in
`mcp_server/resources/itinerary_map.py` and bound to the `render_itinerary`
tool per the MCP Apps extension (SEP-1865). It is published and discoverable —
`resources/list` on a live server returns it.

```text
agent
  ↓
planning/search tools
  ↓
structured itinerary
  ↓
MCP App resource
  ↓
interactive map + itinerary
```

## What renders it, and what does not

**This application's own UI does not.** `apps/web` renders the itinerary with
Leaflet in `ItineraryMap.tsx`, driven by AG-UI `STATE_SNAPSHOT` events. It never
reads the `ui://` resource. That is deliberate: the itinerary is application
state the page already owns, so it can be selected, panned and saved, which an
iframe handed a snapshot cannot do as well.

**An external MCP host does.** Point Claude Desktop or another MCP-Apps-capable
client at `/mcp` and the same tool call renders the map inside that
conversation, with no code written for it.

That split is the honest summary of what MCP Apps buys here: it is a way to give
*other people's clients* a UI, not a way to build your own. A host that does not
implement the extension simply receives the structured itinerary as ordinary
tool output and renders it however it likes — which is exactly what `apps/web`
does.

The document is deliberately dependency-free: MCP App resources are inlined into
the host's sandboxed frame, where a CDN fetch may be blocked by CSP.

Normal application UI should remain normal Next.js components where MCP Apps do
not provide architectural value.

---

# Human Approval

Approval is requested for consequential actions and not for harmless ones.
Searching places needs no approval; saving a plan does.

When the user asks to save, the agent emits an AG-UI custom event and stops:

```json
{"type":"CUSTOM","name":"approval_requested",
 "value":{"action":"save_plan",
          "detail":{"title":"Dinner and live music","estimated_cost":90,"stop_count":3}}}
```

The UI renders a dialog. Confirming re-sends the request with
`forwardedProps.approved = true`, and only then does the agent call `save_plan`.

**Approval is not authorization.** The dialog says so, and the system enforces
it: an approved save still goes agent → MCP → API, and the API checks
`plans:write` against the verified token. A viewer can approve their own save
all day and never write a plan — the agent explains the refusal rather than
retrying.

This is covered deterministically at three layers:
`services/backend/tests/mcp/test_save_plan.py` (MCP),
`services/backend/tests/api/test_plan_service.py` (API), and the
`viewer_cannot_save` eval case.

---

# Persistence

Domain model:

```text
plans              organization_id, created_by_user_id, title, status,
                   start_time, estimated_cost, estimated_walk_distance_km,
                   agent_run_id
plan_stops         plan_id, position, name, category, start/end_time,
                   latitude, longitude, estimated_cost, reason
user_preferences   organization_id, user_id, default_budget, max_walk_km
agent_runs         organization_id, user_id, model, status, latency,
                   tokens, estimated_cost, trace_id
agent_tool_calls   run_id, tool_name, status, latency, idempotency_key, error
```

Every tenant-owned record includes `organization_id`, indexed, and supplied by
the service layer from the verified principal — never from request input.

`plan_stops.reason` carries the agent's justification for each choice, so a
saved plan explains itself without re-running anything.

A saved plan is retrievable through the FastAPI application API with no agent
involved: `GET /plans` and `GET /plans/{id}`, scoped to the caller's
organization. A request for another organization's plan returns 404, not 403 —
a 403 would confirm the id exists.

---

# Failure Cases

The reference application should handle:

- no nearby events,
- third-party search timeout,
- incomplete venue data,
- route provider failure,
- tool authorization failure,
- agent timeout,
- stream interruption,
- persistence failure,
- user cancellation.

Where appropriate, development and automated tests should use deterministic fixture data so third-party instability does not prevent validation of the application itself.

---

# Observability

A completed run should make it possible to inspect:

```text
run_id
trace_id
organization_id
agent
model
latency
token usage
tool calls
tool failures
retries
evaluation results
```

This is part of the reference implementation, not a separate debugging-only architecture.

---

# End-to-End Validation Flow

A release candidate should support this complete path:

1. authenticate,
2. create an evening-planning request,
3. observe streamed progress,
4. render the structured itinerary and map,
5. replan conversationally,
6. save the plan,
7. retrieve the saved plan through the application API,
8. inspect the associated agent trace/evaluation.

Before promoting a staging release:

```bash
make smoke ENV=staging
make staging-check ENV=staging
```

`staging-check` should validate:

- web application loads,
- authentication works,
- agent responds,
- streaming works,
- MCP tools work,
- map renders,
- itinerary can be created,
- persistence works,
- traces are available.

---

# Scope Boundaries

The initial reference application should not require:

- payments,
- rideshare booking,
- multiplayer presence,
- complex social graphs,
- recommendation-model training,
- custom mapping infrastructure,
- large event-ingestion pipelines.

The reference application exists to exercise reusable platform capabilities with the smallest coherent product workflow.
