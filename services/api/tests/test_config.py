"""Configuration validation.

The dev fixture identity is the one piece of the template that would be
dangerous if it leaked into a deployed environment, so its guards are tested
directly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "local",
        "workos_api_key": "",
        "workos_client_id": "",
        "aws_endpoint_url": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestDevFixtureGuard:
    def test_fixture_auth_is_allowed_locally(self) -> None:
        assert _settings(auth_dev_fixture=True).auth_dev_fixture is True

    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_fixture_auth_is_refused_outside_local(self, env: str) -> None:
        with pytest.raises(ValidationError, match="local-only"):
            _settings(
                app_env=env,
                auth_dev_fixture=True,
                workos_api_key="k",
                workos_client_id="c",
            )


class TestDeployedEnvironmentGuards:
    def test_missing_workos_configuration_fails_startup(self) -> None:
        with pytest.raises(ValidationError, match="WORKOS_API_KEY"):
            _settings(app_env="staging")

    def test_localstack_endpoint_is_refused_outside_local(self) -> None:
        with pytest.raises(ValidationError, match="AWS_ENDPOINT_URL"):
            _settings(
                app_env="prod",
                workos_api_key="k",
                workos_client_id="c",
                aws_endpoint_url="http://localhost:4566",
            )

    def test_a_fully_configured_deployed_environment_is_valid(self) -> None:
        settings = _settings(app_env="prod", workos_api_key="k", workos_client_id="c")
        assert settings.is_local is False
        assert settings.aws_endpoint is None


class TestDerivedValues:
    def test_cors_origins_are_split_and_trimmed(self) -> None:
        settings = _settings(api_cors_origins="http://a.test, http://b.test ,")
        assert settings.cors_origins == ["http://a.test", "http://b.test"]

    def test_jwks_url_is_derived_from_the_client_id(self) -> None:
        settings = _settings(workos_client_id="client_123")
        assert settings.jwks_url.endswith("/sso/jwks/client_123")
