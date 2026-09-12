"""Pin the world every backend suite runs in.

`setdefault` is wrong here: the Makefile exports the developer's .env, so a
real provider or credential would leak into the suite — which once made the
agent tests call a real API and pass only because failures fall back silently
(see 93edf1c).

These pins live at the top of the tree, not only in each suite's conftest,
because the three suites now share one pytest session. Collection order decides
which conftest has run by the time a module builds its settings, and `asgi.py`
imports all three packages — so a per-suite pin alone is no longer a guarantee
that another suite's settings were not already constructed from the real
environment. The per-suite conftests keep their own pins as well, so running a
single directory stays hermetic on its own.
"""

from __future__ import annotations

import os

os.environ["APP_ENV"] = "local"

# API: never resolve the fixture identity in tests that assert on auth.
os.environ["AUTH_DEV_FIXTURE"] = "0"

# Agent: no model call, no spend, no nondeterminism.
os.environ["AGENT_MODEL_PROVIDER"] = "scripted"

# MCP: canned datasets instead of live provider APIs.
os.environ["PLACES_PROVIDER"] = "fixture"
os.environ["EVENTS_PROVIDER"] = "fixture"
