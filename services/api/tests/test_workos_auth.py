"""WorkOS access-token verification.

Tokens are minted with a throwaway RSA key and served through a stubbed JWKS
client, so signature verification is genuinely exercised without calling WorkOS.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import workos
from app.auth.permissions import PLANS_WRITE
from app.errors import NotAuthenticated

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


class _StubSigningKey:
    key = _PUBLIC_KEY


class _StubJWKSClient:
    def get_signing_key_from_jwt(self, _token: str) -> _StubSigningKey:
        return _StubSigningKey()


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workos, "_get_jwks_client", lambda: _StubJWKSClient())


def make_token(**claims: Any) -> str:
    payload: dict[str, Any] = {
        "sub": "user_123",
        "org_id": "org_abc",
        "role": "member",
        "email": "person@example.com",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iat": datetime.now(UTC),
    }
    payload.update(claims)
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")


class TestTokenVerification:
    def test_valid_token_yields_a_principal(self) -> None:
        principal = workos.principal_from_access_token(make_token())
        assert principal.user_id == "user_123"
        assert principal.organization_id == "org_abc"
        assert principal.has(PLANS_WRITE)

    def test_expired_token_is_rejected(self) -> None:
        token = make_token(exp=datetime.now(UTC) - timedelta(hours=1))
        with pytest.raises(NotAuthenticated, match="expired"):
            workos.principal_from_access_token(token)

    def test_token_signed_by_another_key_is_rejected(self) -> None:
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {"sub": "user_x", "org_id": "org_x", "exp": datetime.now(UTC) + timedelta(minutes=5)},
            other_key,
            algorithm="RS256",
        )
        with pytest.raises(NotAuthenticated, match="invalid"):
            workos.principal_from_access_token(token)

    def test_unsigned_token_is_rejected(self) -> None:
        """A 'none' algorithm token must never be accepted."""
        token = jwt.encode({"sub": "user_x", "org_id": "org_x"}, key="", algorithm="none")
        with pytest.raises(NotAuthenticated):
            workos.principal_from_access_token(token)

    def test_token_without_an_organization_is_rejected(self) -> None:
        with pytest.raises(NotAuthenticated, match="organization"):
            workos.principal_from_access_token(make_token(org_id=None))


class TestClaimMapping:
    def test_explicit_permission_claims_win_over_role_defaults(self) -> None:
        principal = workos.principal_from_claims(
            {"sub": "u", "org_id": "o", "role": "admin", "permissions": ["plans:read"]}
        )
        assert principal.permissions == frozenset({"plans:read"})
        assert not principal.has(PLANS_WRITE)

    def test_role_defaults_apply_when_workos_sends_no_permissions(self) -> None:
        principal = workos.principal_from_claims({"sub": "u", "org_id": "o", "role": "viewer"})
        assert principal.permissions == frozenset({"plans:read", "preferences:read"})

    def test_no_role_and_no_permissions_grants_nothing(self) -> None:
        principal = workos.principal_from_claims({"sub": "u", "org_id": "o"})
        assert principal.permissions == frozenset()


class TestDevFixtureToken:
    """The fixture token must be inert unless both guards hold."""

    def test_it_is_refused_when_the_fixture_is_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "auth_dev_fixture", False)
        with pytest.raises(NotAuthenticated):
            workos.dev_fixture_principal()

    def test_it_is_refused_outside_a_local_app_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "auth_dev_fixture", True)
        monkeypatch.setattr(settings, "app_env", "prod")
        with pytest.raises(NotAuthenticated):
            workos.dev_fixture_principal()

    def test_it_resolves_locally_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "auth_dev_fixture", True)
        monkeypatch.setattr(settings, "app_env", "local")

        principal = workos.dev_fixture_principal()
        assert principal.organization_id == settings.auth_dev_fixture_org_id
        assert principal.has(PLANS_WRITE)
