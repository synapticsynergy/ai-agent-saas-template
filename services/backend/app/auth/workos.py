"""WorkOS identity verification.

The API never sees a WorkOS session cookie. Trusted callers — the Next.js
server, and the agent runtime acting on a user's behalf — forward the AuthKit
**access token** as ``Authorization: Bearer <jwt>``. This module verifies that
JWT's signature against the WorkOS JWKS and turns its claims into a
:class:`~app.auth.permissions.Principal`.

Why a JWT rather than a shared service secret: the same assertion can travel
Next.js → agent → MCP → API, and every boundary can independently verify it.
No hop has to trust the hop before it, and no hop can forge a tenant.
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient

from app.auth.permissions import Permission, Principal, permissions_for_role
from app.config import settings
from app.errors import NotAuthenticated

_ALGORITHMS = ["RS256"]

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazily build a cached JWKS client.

    ``PyJWKClient`` caches signing keys, which matters on Lambda where a cold
    JWKS fetch would otherwise be on the critical path of every request.
    """
    global _jwks_client
    if _jwks_client is None:
        if not settings.workos_client_id and not settings.workos_jwks_url:
            raise NotAuthenticated(
                "WorkOS is not configured: set WORKOS_CLIENT_ID so access tokens "
                "can be verified. See docs/DEVELOPMENT.md."
            )
        _jwks_client = PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


def reset_jwks_client_cache() -> None:
    """Test hook: drop the memoised JWKS client."""
    global _jwks_client
    _jwks_client = None


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify an AuthKit access token and return its claims."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            leeway=settings.workos_jwt_leeway_seconds,
            options={"require": ["exp", "sub"]},
        )
    except NotAuthenticated:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise NotAuthenticated("Access token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise NotAuthenticated("Access token is invalid.") from exc


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    """Build a Principal from verified WorkOS claims.

    An access token without ``org_id`` belongs to a user who has not selected an
    organization. The template is organization-scoped throughout, so that is an
    authentication failure rather than a request with a null tenant.
    """
    user_id = str(claims.get("sub") or "")
    organization_id = str(claims.get("org_id") or "")

    if not user_id:
        raise NotAuthenticated("Access token is missing a subject claim.")
    if not organization_id:
        raise NotAuthenticated(
            "Access token has no organization context. The user must select an "
            "organization before calling organization-scoped endpoints."
        )

    role = str(claims.get("role") or "")

    # Prefer explicit permission claims from WorkOS. Fall back to the documented
    # role defaults only when the WorkOS environment has no permissions
    # configured yet, so a fresh setup still behaves sensibly.
    claimed: list[str] = claims.get("permissions") or []
    permissions: frozenset[Permission] = (
        frozenset(str(p) for p in claimed) if claimed else permissions_for_role(role)
    )

    return Principal(
        user_id=user_id,
        organization_id=organization_id,
        email=str(claims.get("email") or ""),
        role=role,
        permissions=permissions,
    )


def principal_from_access_token(token: str) -> Principal:
    return principal_from_claims(decode_access_token(token))


def dev_fixture_principal() -> Principal:
    """Deterministic local identity, used only when explicitly enabled.

    Guarded twice: ``Settings`` refuses to construct with ``AUTH_DEV_FIXTURE``
    set outside ``APP_ENV=local``, and this function re-checks. It cannot be
    reached by an unauthenticated request in a deployed environment.
    """
    if not (settings.is_local and settings.auth_dev_fixture):
        raise NotAuthenticated("Authentication required.")

    role = settings.auth_dev_fixture_role
    return Principal(
        user_id=settings.auth_dev_fixture_user_id,
        organization_id=settings.auth_dev_fixture_org_id,
        email=settings.auth_dev_fixture_email,
        role=role,
        permissions=permissions_for_role(role),
    )
