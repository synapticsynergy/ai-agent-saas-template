"""Candidate scoring and budget arithmetic.

Pure functions over plain data. No I/O, no model, no clock — so the reasoning
that decides *which* venue lands in an itinerary is directly unit-testable and
does not regress silently when a prompt changes.
"""

from __future__ import annotations

from saas_contracts.tools import Event, Place

# Ratings dominate when everything is affordable; distance and price act as
# penalties that grow as a candidate strains the constraints.
RATING_WEIGHT = 1.0
DISTANCE_PENALTY_PER_KM = 0.45
BUDGET_STRAIN_PENALTY = 1.2


def score_place(
    place: Place,
    *,
    distance_km: float,
    remaining_budget: float | None,
    preferred_tags: frozenset[str] = frozenset(),
) -> float:
    """Rank a candidate venue. Higher is better.

    A venue the user cannot afford scores below every affordable option rather
    than being filtered out entirely, so a plan is still produced when the
    budget is unrealistic — with an honest cost — instead of returning nothing.
    """
    score = place.rating * RATING_WEIGHT
    score -= distance_km * DISTANCE_PENALTY_PER_KM

    if preferred_tags:
        matches = preferred_tags & {tag.lower() for tag in place.tags}
        score += 0.35 * len(matches)

    score += _budget_term(place.typical_cost_per_person, remaining_budget)
    return round(score, 4)


def score_event(
    event: Event,
    *,
    distance_km: float,
    remaining_budget: float | None,
    preferred_genre: str = "",
) -> float:
    score = 3.5 - distance_km * DISTANCE_PENALTY_PER_KM

    if preferred_genre and event.genre.lower() == preferred_genre.lower():
        score += 1.5

    score += _budget_term(event.ticket_price, remaining_budget)
    if remaining_budget is not None and event.ticket_price == 0:
        score += 0.5

    return round(score, 4)


def _budget_term(cost: float, allowance: float | None) -> float:
    """Score contribution from price, given what the stop can afford.

    Over-budget candidates are penalised *in proportion to the overage*, not by
    a flat amount. A flat penalty makes every unaffordable option equally bad,
    so a higher rating then picks the most expensive one — exactly backwards
    when the user has asked to keep costs down.
    """
    if allowance is None:
        return 0.0

    if cost > allowance:
        overage_ratio = (cost - allowance) / max(allowance, 1.0)
        return -BUDGET_STRAIN_PENALTY * (1.0 + overage_ratio)

    # Mild preference for leaving room for later stops.
    headroom = 1 - (cost / max(allowance, 1e-6))
    return 0.4 * headroom


def total_cost(costs: list[float], party_size: int = 1) -> float:
    """Total spend for the party."""
    return round(sum(costs) * party_size, 2)


def within_budget(costs: list[float], budget: float | None, party_size: int = 1) -> bool:
    if budget is None:
        return True
    return total_cost(costs, party_size) <= budget


# Rough relative spend per category, used to divide a budget across stops.
CATEGORY_BUDGET_WEIGHTS: dict[str, float] = {
    "dinner": 3.0,
    "music": 2.0,
    "drinks": 1.5,
    "activity": 1.5,
    "dessert": 1.0,
    "coffee": 0.7,
}


def allocate_budget(remaining: float, remaining_categories: list[str]) -> float:
    """How much of the remaining budget this stop may spend.

    Without this, a greedy planner spends the whole budget on the first stop and
    then has nothing left, producing a technically-in-budget plan that is a
    dinner and two disappointments. Unspent allowance carries forward, so a
    cheap first stop still leaves room later.
    """
    if not remaining_categories:
        return remaining

    weights = [CATEGORY_BUDGET_WEIGHTS.get(c, 1.0) for c in remaining_categories]
    total_weight = sum(weights)
    if total_weight <= 0:
        return remaining

    return round(remaining * (weights[0] / total_weight), 2)


def cheapest_first(places: list[Place]) -> list[Place]:
    """Order by cost, then rating, then id — stable and deterministic."""
    return sorted(places, key=lambda p: (p.typical_cost_per_person, -p.rating, p.id))
