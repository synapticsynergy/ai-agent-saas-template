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

The itinerary should be structured application state rather than information embedded only in assistant prose.

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
      ┌───┴────┐
      ▼        ▼
 FastAPI     AgentCore
 Lambda      Strands
      │        │
      │       MCP
      │        ▼
      │    Gateway / Tools
      └──────┬─┘
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

The primary MCP App can be the interactive itinerary/map.

Conceptually:

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

This provides a concrete example of a tool producing an interactive application surface rather than only text.

Normal application UI should remain normal Next.js components where MCP Apps do not provide architectural value.

---

# Human Approval

Use approval for consequential or user-commitment actions.

Example:

```text
I found a ticketed show for $28 that fits the plan.

[ Skip ] [ Add to plan ]
```

Do not require approval for harmless discovery operations such as searching places.

Approval does not replace authorization. The backend still verifies the authenticated user's permission before executing protected actions.

---

# Persistence

Minimum domain model:

```text
plans
plan_stops
user_preferences
agent_runs
agent_tool_calls
```

Every tenant-owned record includes:

```text
organization_id
```

A saved plan should be retrievable through the deterministic FastAPI application API independently of the agent.

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
