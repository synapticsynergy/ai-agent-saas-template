"""Application configuration.

Every setting is read from the environment once at import time and validated
eagerly, so a misconfigured deployment fails at startup with a readable error
instead of at the first request that happens to need the value.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db_url import to_async_url, to_sync_url

AppEnv = Literal["local", "dev", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = "local"
    log_level: str = "INFO"

    # One URL, as every managed Postgres hands it out. The driver-specific
    # forms the app and Alembic need are derived — see app.db_url.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
    # Optional: point Alembic at a different endpoint (a direct connection
    # when the app goes through a pooler). Read from DATABASE_SYNC_URL.
    database_sync_url_override: str = Field(default="", validation_alias="DATABASE_SYNC_URL")
    database_pool_size: int = 5
    database_echo: bool = False

    api_cors_origins: str = "http://localhost:3000"

    workos_api_key: str = ""
    workos_client_id: str = ""
    workos_jwks_url: str = ""
    workos_jwt_leeway_seconds: int = 30

    auth_dev_fixture: bool = False
    # Opaque bearer token that resolves to the fixture identity. Having local
    # development carry a token at every hop keeps the identity path shaped
    # exactly like production instead of a special no-token code path.
    auth_dev_fixture_token: str = "local-dev-fixture-token"  # noqa: S105
    auth_dev_fixture_user_id: str = "user_local_demo"
    auth_dev_fixture_org_id: str = "org_local_demo"
    auth_dev_fixture_email: str = "demo@example.com"
    auth_dev_fixture_role: str = "member"

    aws_region: str = "us-west-2"
    aws_endpoint_url: str = ""
    s3_bucket: str = "ai-agent-saas-local"
    dynamodb_enabled: bool = False
    dynamodb_table: str = "ai-agent-saas-local"

    provider_timeout_seconds: float = 8.0

    @property
    def jwks_url(self) -> str:
        return self.workos_jwks_url or (f"https://api.workos.com/sso/jwks/{self.workos_client_id}")

    @property
    def database_async_url(self) -> str:
        return to_async_url(self.database_url)

    @property
    def database_sync_url(self) -> str:
        return self.database_sync_url_override or to_sync_url(self.database_url)

    @field_validator("api_cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def aws_endpoint(self) -> str | None:
        """LocalStack endpoint override, or None to use real AWS endpoints."""
        return self.aws_endpoint_url or None

    @model_validator(mode="after")
    def _validate_environment(self) -> Settings:
        if self.auth_dev_fixture and self.app_env != "local":
            raise ValueError(
                "AUTH_DEV_FIXTURE is enabled but APP_ENV is "
                f"'{self.app_env}'. The fixture identity is a local-only "
                "development aid and must never be reachable outside APP_ENV=local."
            )

        if not self.is_local:
            missing = [
                name
                for name, value in (
                    ("WORKOS_API_KEY", self.workos_api_key),
                    ("WORKOS_CLIENT_ID", self.workos_client_id),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"APP_ENV={self.app_env} requires these variables to be set: "
                    + ", ".join(missing)
                )
            if self.aws_endpoint_url:
                raise ValueError(
                    "AWS_ENDPOINT_URL points the AWS SDK at a local emulator and "
                    f"must be empty when APP_ENV={self.app_env}."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:  # pragma: no cover - startup failure path
        raise SystemExit(f"Invalid API configuration:\n{exc}") from exc


settings = get_settings()
