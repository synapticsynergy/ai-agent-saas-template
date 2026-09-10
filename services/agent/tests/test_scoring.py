"""Scoring and budget arithmetic."""

from __future__ import annotations

import pytest

from agent_app.workflows.scoring import (
    allocate_budget,
    cheapest_first,
    score_place,
    total_cost,
    within_budget,
)
from tests.conftest import place


class TestScorePlace:
    def test_higher_rating_scores_higher_all_else_equal(self) -> None:
        good = place("a", "Good", "dinner", 20.0, 4.8)
        okay = place("b", "Okay", "dinner", 20.0, 3.2)
        assert score_place(good, distance_km=0.5, remaining_budget=50) > score_place(
            okay, distance_km=0.5, remaining_budget=50
        )

    def test_distance_is_a_penalty(self) -> None:
        venue = place("a", "Venue", "dinner", 20.0, 4.5)
        assert score_place(venue, distance_km=0.2, remaining_budget=50) > score_place(
            venue, distance_km=2.0, remaining_budget=50
        )

    def test_preferred_tags_are_a_bonus(self) -> None:
        tagged = place("a", "Vegan spot", "dinner", 20.0, 4.0, tags=["vegan"])
        plain = place("b", "Plain", "dinner", 20.0, 4.0)
        assert score_place(
            tagged, distance_km=0.5, remaining_budget=50, preferred_tags=frozenset({"vegan"})
        ) > score_place(
            plain, distance_km=0.5, remaining_budget=50, preferred_tags=frozenset({"vegan"})
        )

    def test_over_budget_scores_below_affordable(self) -> None:
        affordable = place("a", "Cheap", "dinner", 20.0, 3.0)
        expensive = place("b", "Pricey", "dinner", 90.0, 5.0)
        assert score_place(expensive, distance_km=0.5, remaining_budget=30) < score_place(
            affordable, distance_km=0.5, remaining_budget=30
        )

    def test_among_unaffordable_options_the_cheaper_one_wins(self) -> None:
        """A flat over-budget penalty would let rating pick the priciest option."""
        slightly_over = place("a", "Slightly over", "dinner", 35.0, 3.0)
        wildly_over = place("b", "Wildly over", "dinner", 200.0, 5.0)
        assert score_place(slightly_over, distance_km=0.5, remaining_budget=30) > score_place(
            wildly_over, distance_km=0.5, remaining_budget=30
        )

    def test_no_budget_means_no_price_influence(self) -> None:
        cheap = place("a", "Cheap", "dinner", 5.0, 4.0)
        pricey = place("b", "Pricey", "dinner", 90.0, 4.0)
        assert score_place(cheap, distance_km=0.5, remaining_budget=None) == score_place(
            pricey, distance_km=0.5, remaining_budget=None
        )


class TestBudgetArithmetic:
    def test_total_cost_multiplies_by_party_size(self) -> None:
        assert total_cost([10.0, 20.0], party_size=3) == 90.0

    def test_within_budget(self) -> None:
        assert within_budget([30.0, 20.0], budget=100.0, party_size=1)
        assert not within_budget([30.0, 20.0], budget=40.0, party_size=1)

    def test_no_budget_is_always_within_budget(self) -> None:
        assert within_budget([1000.0], budget=None)

    def test_party_size_counts_against_the_budget(self) -> None:
        assert not within_budget([30.0], budget=50.0, party_size=2)


class TestAllocateBudget:
    def test_allocation_leaves_room_for_later_stops(self) -> None:
        allowance = allocate_budget(100.0, ["dinner", "music", "drinks"])
        assert 0 < allowance < 100.0

    def test_dinner_gets_more_than_coffee(self) -> None:
        dinner = allocate_budget(100.0, ["dinner", "coffee"])
        coffee = allocate_budget(100.0, ["coffee", "dinner"])
        assert dinner > coffee

    def test_the_last_stop_may_spend_everything_left(self) -> None:
        assert allocate_budget(40.0, ["drinks"]) == 40.0

    def test_no_remaining_categories_returns_the_remainder(self) -> None:
        assert allocate_budget(25.0, []) == 25.0


class TestCheapestFirst:
    def test_orders_by_cost(self) -> None:
        ordered = cheapest_first(
            [
                place("c", "Pricey", "dinner", 80.0, 4.9),
                place("a", "Cheap", "dinner", 12.0, 3.5),
                place("b", "Mid", "dinner", 40.0, 4.2),
            ]
        )
        assert [p.id for p in ordered] == ["a", "b", "c"]

    def test_ties_break_deterministically(self) -> None:
        first = cheapest_first(
            [place("z", "Z", "dinner", 20.0, 4.0), place("a", "A", "dinner", 20.0, 4.0)]
        )
        second = cheapest_first(
            [place("a", "A", "dinner", 20.0, 4.0), place("z", "Z", "dinner", 20.0, 4.0)]
        )
        assert [p.id for p in first] == [p.id for p in second]


def test_scoring_never_returns_nan() -> None:
    venue = place("a", "Venue", "dinner", 0.0, 0.0)
    for budget in (None, 0.0, 1.0, 1000.0):
        score = score_place(venue, distance_km=0.0, remaining_budget=budget)
        assert score == pytest.approx(score)  # NaN != NaN
