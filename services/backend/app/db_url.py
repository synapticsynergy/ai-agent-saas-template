"""Derive driver-specific SQLAlchemy URLs from one Postgres URL.

Managed Postgres (Railway, Neon, RDS) provides ``postgresql://``. SQLAlchemy
needs the driver in the scheme: asyncpg for the application, psycopg for
Alembic. Rewriting the scheme is the whole job; nothing else in the URL is
touched, so credentials, ports and query strings pass through untouched.
"""

from __future__ import annotations

_ACCEPTED_SCHEMES = ("postgresql+asyncpg", "postgresql+psycopg", "postgresql", "postgres")


def _split_scheme(url: str) -> str:
    scheme, sep, rest = url.partition("://")
    if not sep or scheme not in _ACCEPTED_SCHEMES:
        raise ValueError(
            f"DATABASE_URL must be a Postgres URL (one of {', '.join(_ACCEPTED_SCHEMES)}://); "
            f"got scheme {scheme!r}."
        )
    return rest


def to_async_url(url: str) -> str:
    """The URL with the asyncpg driver, for the application's engine."""
    return f"postgresql+asyncpg://{_split_scheme(url)}"


def to_sync_url(url: str) -> str:
    """The URL with the psycopg driver, for Alembic and other sync tooling."""
    return f"postgresql+psycopg://{_split_scheme(url)}"
