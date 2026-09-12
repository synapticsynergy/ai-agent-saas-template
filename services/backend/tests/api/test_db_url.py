"""One DATABASE_URL, two drivers.

Managed Postgres providers hand out a plain ``postgresql://`` URL. The app
needs asyncpg at runtime and psycopg for Alembic, so both are derived from the
one URL rather than asking operators to spell two.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.db_url import to_async_url, to_sync_url

PLAIN = "postgresql://u:p@db.example:5432/app"


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://u:p@db.example:5432/app",
        "postgres://u:p@db.example:5432/app",
        "postgresql+asyncpg://u:p@db.example:5432/app",
        "postgresql+psycopg://u:p@db.example:5432/app",
    ],
)
def test_every_accepted_scheme_derives_both_drivers(given: str) -> None:
    assert to_async_url(given) == "postgresql+asyncpg://u:p@db.example:5432/app"
    assert to_sync_url(given) == "postgresql+psycopg://u:p@db.example:5432/app"


def test_query_string_and_credentials_survive() -> None:
    url = "postgresql://u:p%40ss@db.example/app?sslmode=require"
    # asyncpg spells the libpq sslmode parameter `ssl`; psycopg takes it as-is.
    assert to_async_url(url) == "postgresql+asyncpg://u:p%40ss@db.example/app?ssl=require"
    assert to_sync_url(url) == "postgresql+psycopg://u:p%40ss@db.example/app?sslmode=require"


def test_other_query_parameters_pass_through_unchanged() -> None:
    url = "postgresql://u:p@db.example/app?sslmode=verify-full&application_name=api"
    assert (
        to_async_url(url)
        == "postgresql+asyncpg://u:p@db.example/app?ssl=verify-full&application_name=api"
    )


def test_no_query_string_means_no_question_mark() -> None:
    assert (
        to_async_url("postgresql://u:p@db.example/app") == "postgresql+asyncpg://u:p@db.example/app"
    )


def test_non_postgres_urls_are_rejected() -> None:
    with pytest.raises(ValueError, match="Postgres"):
        to_async_url("mysql://u:p@db.example/app")


def test_alembic_main_option_survives_a_percent_encoded_password() -> None:
    """Alembic stores the URL in a ConfigParser, which interpolates '%'."""
    from alembic.config import Config

    url = "postgresql+psycopg://u:p%40ss@db.example/app"
    config = Config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    assert config.get_main_option("sqlalchemy.url") == url


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": "local",
        "auth_dev_fixture": False,
        "workos_api_key": "",
        "workos_client_id": "",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestSettingsProperties:
    def test_both_urls_derive_from_database_url(self) -> None:
        settings = _settings(database_url=PLAIN)
        assert settings.database_async_url == "postgresql+asyncpg://u:p@db.example:5432/app"
        assert settings.database_sync_url == "postgresql+psycopg://u:p@db.example:5432/app"

    def test_sync_override_wins_when_set(self) -> None:
        settings = _settings(
            database_url=PLAIN,
            DATABASE_SYNC_URL="postgresql+psycopg://u:p@pooler.example:6432/app",
        )
        assert settings.database_sync_url == "postgresql+psycopg://u:p@pooler.example:6432/app"
        assert settings.database_async_url == "postgresql+asyncpg://u:p@db.example:5432/app"
