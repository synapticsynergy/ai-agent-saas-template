"""Derive driver-specific SQLAlchemy URLs from one Postgres URL.

Managed Postgres (Railway, Neon, RDS) provides ``postgresql://``. SQLAlchemy
needs the driver in the scheme: asyncpg for the application, psycopg for
Alembic. Rewriting the scheme is most of the job; the one other thing asyncpg
needs is its own spelling of ``sslmode`` (asyncpg takes ``ssl``, psycopg takes
``sslmode`` as-is). Everything else in the URL — credentials, host, path, and
any other query parameters — passes through untouched.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    """The URL with the asyncpg driver, for the application's engine.

    asyncpg spells the libpq ``sslmode`` parameter ``ssl``; that rename is
    applied here, leaving every other query parameter untouched.
    """
    rest = f"postgresql+asyncpg://{_split_scheme(url)}"
    scheme, netloc, path, query, fragment = urlsplit(rest)
    params = parse_qsl(query, keep_blank_values=True)
    params = [("ssl" if key == "sslmode" else key, value) for key, value in params]
    new_query = urlencode(params)
    return urlunsplit((scheme, netloc, path, new_query, fragment))


def to_sync_url(url: str) -> str:
    """The URL with the psycopg driver, for Alembic and other sync tooling."""
    return f"postgresql+psycopg://{_split_scheme(url)}"
