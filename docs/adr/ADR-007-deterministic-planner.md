# ADR-007: The Planner Is Deterministic

**Status:** Accepted

## Context

The reference agent has to turn "dinner, live music and drinks, walkable, under
$100" into a concrete itinerary. The straightforward implementation gives the
model the tools and lets it assemble the plan through a reasoning loop.

That works, and it is what most agent demos do. It also means the parts of the
behaviour a user would complain about — the plan costs more than they asked for,
two stops overlap, the walk is further than promised — live inside the model,
where they cannot be unit-tested and regress silently when a prompt changes.

## Decision

Split the run:

- **The model interprets.** Claude turns free text into a `PlanningRequest` via
  structured output (`agent_app/interpreter.py`), through the Anthropic SDK
  against either the Claude API or Bedrock. It is not allowed to choose the
  location or the clock; those are re-pinned from the browser and the server
  after every call.
- **Ordinary code plans.** `agent_app/workflows/planner.py` calls the tools,
  scores candidates, allocates budget across stops, orders and times them, and
  checks the route. No model involvement.

Conversational revision follows the same rule: "make it cheaper" adjusts the
`PlanningRequest` and rebuilds, rather than asking a model to edit structured
state in place.

## Consequences

Positive:

- the planning logic is unit-testable with exact assertions,
- itinerary invariants — ordering, no overlaps, budget arithmetic — hold by
  construction rather than by instruction,
- a revision cannot quietly violate a constraint the original plan honoured,
- the deterministic layer runs without AWS credentials, so the reference app,
  the E2E suite and part of the eval suite work with no model at all,
- it is a worked example of the template's own central principle.

Negative:

- the agent is less flexible than a free reasoning loop: a request the parser
  does not understand degrades to defaults rather than being reasoned about,
- adding a planning capability means writing code, not editing a prompt,
- the split has to be explained, because "the agent" doing arithmetic in Python
  surprises people who expect the model to do everything.

## Evidence

Two defects the deterministic layer's tests caught, which a prose-asserting
suite would have missed:

- Over-budget candidates were penalised by a flat amount, so a higher rating
  then selected the *most* expensive unaffordable venue.
- Atmosphere preferences ("quiet", "date night") were passed to search as a hard
  filter, which discarded every affordable option and produced plans that missed
  the stated budget.

Both were found by assertions on numbers, not on wording.
