"""Agent configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ModelProvider = Literal["anthropic", "bedrock", "scripted"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"

    agent_name: str = "plan-my-evening"
    agent_port: int = 8080

    api_base_url: str = "http://localhost:8000"
    mcp_server_url: str = "http://localhost:8090/mcp"
    agentcore_gateway_url: str = ""

    # Claude API, called directly. An empty key is not an error: the Anthropic
    # SDK also resolves ANTHROPIC_API_KEY from the process environment,
    # ANTHROPIC_AUTH_TOKEN, and `ant auth login` profiles.
    anthropic_api_key: str = ""
    anthropic_model_id: str = "claude-opus-5"
    # Generous on purpose: current models think before answering and those
    # tokens count against this cap. Only tokens actually generated are billed.
    anthropic_max_tokens: int = 16000

    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_region: str = "us-west-2"
    bedrock_max_tokens: int = 4096
    # Unset by default. Claude Opus 5 and Sonnet 5 reject sampling parameters
    # with a 400, which the interpreter would swallow as a fallback to rules —
    # so a default here would quietly switch the model off.
    bedrock_temperature: float | None = None

    # Which model interprets requests and writes replies:
    #   anthropic — Claude API directly
    #   bedrock   — Claude on Amazon Bedrock
    #   scripted  — no model call; rule-based parsing and composed replies, so
    #               the reference app, E2E suite and deterministic evals run
    #               without credentials. Refused outside APP_ENV=local, for the
    #               same reason AUTH_DEV_FIXTURE is.
    agent_model_provider: ModelProvider = "bedrock"

    agent_timeout_seconds: float = 120.0
    tool_timeout_seconds: float = 20.0
    max_agent_iterations: int = 12

    default_latitude: float = 45.5231
    default_longitude: float = -122.6765
    default_timezone: str = "America/Los_Angeles"

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def tools_url(self) -> str:
        """Prefer AgentCore Gateway when configured, else the MCP server directly."""
        return self.agentcore_gateway_url or self.mcp_server_url

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        if self.agent_model_provider == "scripted" and self.app_env != "local":
            raise ValueError(
                "AGENT_MODEL_PROVIDER=scripted bypasses model inference and is a "
                f"local-development and test aid only. APP_ENV is '{self.app_env}'."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:  # pragma: no cover - startup failure path
        raise SystemExit(f"Invalid agent configuration:\n{exc}") from exc


settings = get_settings()
