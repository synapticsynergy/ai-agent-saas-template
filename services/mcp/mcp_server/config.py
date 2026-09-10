"""MCP server configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["fixture", "http"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8090

    api_base_url: str = "http://localhost:8000"

    places_provider: ProviderName = "fixture"
    events_provider: ProviderName = "fixture"
    route_provider: ProviderName = "fixture"

    places_api_url: str = ""
    places_api_key: str = ""
    events_api_url: str = ""
    events_api_key: str = ""
    provider_timeout_seconds: float = 8.0

    default_timezone: str = "America/Los_Angeles"

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        for name, provider, url in (
            ("PLACES", self.places_provider, self.places_api_url),
            ("EVENTS", self.events_provider, self.events_api_url),
        ):
            if provider == "http" and not url:
                raise ValueError(f"{name}_PROVIDER=http requires {name}_API_URL to be set.")
        return self


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:  # pragma: no cover - startup failure path
        raise SystemExit(f"Invalid MCP server configuration:\n{exc}") from exc


settings = get_settings()
