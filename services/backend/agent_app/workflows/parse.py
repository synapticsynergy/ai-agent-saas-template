"""Turn a free-text request into structured planning constraints.

Two implementations, one interface:

* :func:`parse_with_rules` — deterministic keyword extraction. Used when
  ``AGENT_MODEL_PROVIDER=scripted`` (local development and tests without model
  credentials) and as the fallback when a model call fails.
* :class:`agent_app.interpreter.ModelInterpreter` asks the model for the same
  structure.

Both produce a :class:`PlanningRequest`, so everything downstream is identical
regardless of which one ran. The rule parser is not a "fake agent" — it is the
degraded mode for one narrow step, and it never touches itinerary construction.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from saas_contracts.plan import StopCategory

from agent_app.workflows.request import PlanningRequest

_CATEGORY_KEYWORDS: dict[StopCategory, tuple[str, ...]] = {
    "dinner": ("dinner", "eat", "food", "restaurant", "meal", "supper"),
    "music": ("music", "show", "concert", "gig", "band", "jazz", "live"),
    "drinks": ("drinks", "bar", "cocktail", "beer", "wine", "pub"),
    "dessert": ("dessert", "sweet", "ice cream", "pie"),
    "coffee": ("coffee", "espresso", "cafe"),
    "activity": ("activity", "arcade", "games", "bowling", "museum"),
}

_GENRES = (
    "jazz",
    "rock",
    "soul",
    "folk",
    "blues",
    "electronic",
    "hip hop",
    "classical",
    "country",
)

_BUDGET_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)|under\s+(\d+)|below\s+(\d+)", re.IGNORECASE)
_WALK_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(km|kilometres?|kilometers?|miles?|mi)\b", re.IGNORECASE)
_PARTY_RE = re.compile(r"\b(?:for\s+)?(\d{1,2})\s+(?:people|friends|of us|guests)\b", re.IGNORECASE)

# Dietary needs exclude a venue outright.
_DIETARY_KEYWORDS = {
    "vegan": "vegan",
    "vegetarian": "vegetarian-friendly",
}

# Atmosphere is a preference: it ranks candidates, it does not remove them.
_PREFERENCE_KEYWORDS = {
    "date night": "date-night",
    "quiet": "quiet",
    "patio": "patio",
    "rooftop": "rooftop",
    "seafood": "seafood",
    "casual": "casual",
    "cocktails": "cocktails",
}

DEFAULT_CATEGORIES: list[StopCategory] = ["dinner", "music", "drinks"]


def parse_with_rules(
    text: str,
    *,
    latitude: float,
    longitude: float,
    start_time: datetime | None = None,
) -> PlanningRequest:
    lowered = text.lower()

    categories = [
        category
        for category, keywords in _CATEGORY_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    if not categories:
        categories = list(DEFAULT_CATEGORIES)
    else:
        # Preserve a sensible evening order rather than dict iteration order.
        order = ["coffee", "dinner", "activity", "music", "dessert", "drinks"]
        categories = [c for c in order if c in categories]

    return PlanningRequest(
        latitude=latitude,
        longitude=longitude,
        start_time=start_time or _default_start(),
        categories=categories,
        budget=_parse_budget(text),
        max_walk_km=_parse_walk_km(text),
        music_genre=next((genre for genre in _GENRES if genre in lowered), ""),
        dietary_tags=[tag for phrase, tag in _DIETARY_KEYWORDS.items() if phrase in lowered],
        preference_tags=[tag for phrase, tag in _PREFERENCE_KEYWORDS.items() if phrase in lowered],
        party_size=_parse_party_size(text),
    )


def _parse_budget(text: str) -> float | None:
    match = _BUDGET_RE.search(text)
    if not match:
        return None
    value = next((group for group in match.groups() if group), None)
    return float(value) if value else None


def _parse_walk_km(text: str) -> float:
    match = _WALK_RE.search(text)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        return round(value * 1.60934, 2) if unit.startswith("mi") else value

    if "walkable" in text.lower() or "walking distance" in text.lower():
        return 1.5
    return 2.5


def _parse_party_size(text: str) -> int:
    match = _PARTY_RE.search(text)
    if not match:
        return 2
    return max(1, min(20, int(match.group(1))))


def _default_start() -> datetime:
    """Next 7pm, in whatever timezone the caller's start_time would have used."""
    now = datetime.now().astimezone()
    start = now.replace(hour=19, minute=0, second=0, microsecond=0)
    return start if start > now else start + timedelta(days=1)
