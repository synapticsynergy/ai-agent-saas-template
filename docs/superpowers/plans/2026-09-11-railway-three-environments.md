# Railway + Vercel Three Environments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the backend to Railway and the web app to Vercel across `dev`, `staging` and `main`, and remove every AWS remnant from the default path.

**Architecture:** One `railway.json` at the repo root describes the backend service (Dockerfile build, `/health` check, Alembic as the pre-deploy command). Three Railway environments track three branches; Vercel does the same natively. The only code change is that the backend derives its async and sync database URLs from a single plain `DATABASE_URL`. Everything AWS-flavoured (LocalStack, S3, DynamoDB, Bedrock, Terraform CI job, Fly and Render configs) is deleted from the default path; it lives on under `advanced/`.

**Tech Stack:** FastAPI + pydantic-settings, SQLAlchemy async + Alembic, uv, pytest, Docker Compose, GitHub Actions, Railway, Vercel.

**Spec:** `docs/superpowers/specs/2026-09-11-railway-three-environments-design.md`

## Global Constraints

- Nothing under `advanced/` is modified except one sentence added to `advanced/README.md` (Task 8).
- `APP_ENV` literal values in the backend stay `local | dev | staging | prod`.
- `ModelProvider` becomes exactly `Literal["anthropic", "scripted"]`.
- The `runtime` Dockerfile stage stays the last stage in the file.
- All work happens on branch `simplify/railway-three-envs`, cut from `main`.
- Python commands run from `services/backend` with `uv run`; repo-level commands run from the repo root with `make`.
- Every task ends with `make check` green before its commit (from the repo root, it runs format, lint, types, contracts and unit tests).

---

## File Structure

| Path | Responsibility |
|---|---|
| `services/backend/app/db_url.py` (new) | Pure functions that rewrite a Postgres URL's scheme to the asyncpg or psycopg driver. |
| `services/backend/tests/api/test_db_url.py` (new) | Tests for those functions and for the settings properties built on them. |
| `services/backend/app/config.py` | Gains `database_async_url` / `database_sync_url` properties; loses every `aws_*`, `s3_*`, `dynamodb_*` setting and the `AWS_ENDPOINT_URL` validator. |
| `services/backend/app/persistence/postgres.py`, `services/backend/alembic/env.py` | Switch to the derived properties. |
| `services/backend/app/routes/health.py` | Readiness reports `database` only. |
| `services/backend/app/persistence/s3.py`, `dynamo.py`, `tests/integration/test_s3.py`, `scripts/localstack/` | Deleted. |
| `services/backend/agent_app/config.py`, `agent_app/interpreter.py`, `tests/agent/test_parse_and_replan.py` | Bedrock removed. |
| `services/backend/pyproject.toml`, `uv.lock` | `boto3` and `boto3-stubs` removed. |
| `railway.json` (new) | Railway service definition. `fly.toml`, `render.yaml` deleted. |
| `docker-compose.yml`, `scripts/require-infra.sh`, `Makefile`, `.github/workflows/ci.yml`, `.env.example` | LocalStack and AWS variables removed; single `DATABASE_URL`. |
| `docs/DEPLOYMENT.md` (rewritten), `docs/adr/ADR-010-railway-and-vercel.md` (new), `docs/adr/ADR-004-localstack-scope.md`, `docs/DEVELOPMENT.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/TEMPLATE_CHECKLIST.md`, `docs/GIT_WORKFLOW.md`, `README.md`, `advanced/README.md` | Documentation. |

---

### Task 1: Branch, and derive both database URLs from one `DATABASE_URL`

**Files:**
- Create: `services/backend/app/db_url.py`
- Create: `services/backend/tests/api/test_db_url.py`
- Modify: `services/backend/app/config.py:30-31`
- Modify: `services/backend/app/persistence/postgres.py:19-20`
- Modify: `services/backend/alembic/env.py:1-6,19,29`
- Modify: `services/backend/alembic.ini:5`

**Interfaces:**
- Produces: `app.db_url.to_async_url(url: str) -> str`, `app.db_url.to_sync_url(url: str) -> str`, `Settings.database_async_url: str` (property), `Settings.database_sync_url: str` (property). The optional override env var is `DATABASE_SYNC_URL`, read into the field `database_sync_url_override`.
- Later tasks (compose, CI, `.env.example`, docs) rely on `DATABASE_URL` accepting a plain `postgresql://` URL.

- [ ] **Step 1: Cut the working branch from main**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
git checkout main && git pull
git checkout -b simplify/railway-three-envs
```

- [ ] **Step 2: Write the failing tests**

Create `services/backend/tests/api/test_db_url.py`:

```python
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
    assert to_async_url(url) == "postgresql+asyncpg://u:p%40ss@db.example/app?sslmode=require"


def test_non_postgres_urls_are_rejected() -> None:
    with pytest.raises(ValueError, match="Postgres"):
        to_async_url("mysql://u:p@db.example/app")


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
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
cd services/backend && uv run pytest tests/api/test_db_url.py -q
```

Expected: `ImportError` / `ModuleNotFoundError: No module named 'app.db_url'`.

- [ ] **Step 4: Implement `app/db_url.py`**

```python
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
```

- [ ] **Step 5: Wire the properties into `app/config.py`**

Replace lines 30–31:

```python
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    database_sync_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/app"
```

with:

```python
    # One URL, as every managed Postgres hands it out. The driver-specific
    # forms the app and Alembic need are derived — see app.db_url.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
    # Optional: point Alembic at a different endpoint (a direct connection
    # when the app goes through a pooler). Read from DATABASE_SYNC_URL.
    database_sync_url_override: str = Field(default="", validation_alias="DATABASE_SYNC_URL")
```

Add `Field` to the pydantic import on line 13:

```python
from pydantic import Field, ValidationError, field_validator, model_validator
```

Add `from app.db_url import to_async_url, to_sync_url` after the pydantic-settings import.

Add two properties directly below the `jwks_url` property:

```python
    @property
    def database_async_url(self) -> str:
        return to_async_url(self.database_url)

    @property
    def database_sync_url(self) -> str:
        return self.database_sync_url_override or to_sync_url(self.database_url)
```

- [ ] **Step 6: Switch the consumers**

`services/backend/app/persistence/postgres.py` line 20: `settings.database_url,` → `settings.database_async_url,`. Also replace the comment on lines 17–18 (it still talks about Lambda) with:

```python
# A small pool per instance: horizontal replicas each carry their own, and
# many small pools beat one large one against a managed Postgres.
```

`services/backend/alembic/env.py`: lines 19 and 29 already read `settings.database_sync_url`, which is now the property. Replace the docstring lines 3–5 with:

```python
Migrations run against the *synchronous* driver while the application uses
asyncpg. Both URLs derive from one ``DATABASE_URL``; ``DATABASE_SYNC_URL`` is an
optional override. Keeping migrations synchronous avoids an event loop inside
deploy tooling for no benefit.
```

`services/backend/alembic.ini` line 5: change `set from DATABASE_SYNC_URL in alembic/env.py` to `derived from DATABASE_URL in alembic/env.py`.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd services/backend && uv run pytest tests/api/test_db_url.py tests/api/test_config.py -q
```

Expected: all pass.

- [ ] **Step 8: Full fast suite**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template && make check
```

Expected: green. If mypy complains about `Field(validation_alias=...)`, the fix is the import in Step 5, not an ignore.

- [ ] **Step 9: Commit**

```bash
git add services/backend/app/db_url.py services/backend/tests/api/test_db_url.py \
        services/backend/app/config.py services/backend/app/persistence/postgres.py \
        services/backend/alembic/env.py services/backend/alembic.ini
git commit -m "feat(backend): derive async and sync database URLs from one DATABASE_URL

Managed Postgres provides postgresql://. The app now accepts that (and the
driver-prefixed spellings) and derives the asyncpg and psycopg forms itself.
DATABASE_SYNC_URL remains an optional override.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Remove the S3 and DynamoDB adapters and every AWS setting

**Files:**
- Delete: `services/backend/app/persistence/s3.py`, `services/backend/app/persistence/dynamo.py`, `tests/integration/test_s3.py`
- Modify: `services/backend/app/config.py` (aws/s3/dynamo settings, `aws_endpoint` property, validator branch)
- Modify: `services/backend/app/routes/health.py:8,31`
- Modify: `services/backend/tests/api/test_config.py:26,55-69`
- Modify: `services/backend/tests/api/test_routes.py` (add readiness test)
- Modify: `services/backend/pyproject.toml:27,49`

**Interfaces:**
- Consumes: nothing new.
- Produces: `/health/ready` body `checks == {"database": bool}`. `Settings` no longer has `aws_region`, `aws_endpoint_url`, `aws_endpoint`, `s3_bucket`, `dynamodb_enabled`, `dynamodb_table`.

- [ ] **Step 1: Write the failing readiness test**

Append to `TestHealth` in `services/backend/tests/api/test_routes.py`:

```python
    async def test_readiness_reports_only_the_database(self, client_factory: Any) -> None:
        async with client_factory(None) as client:
            response = await client.get("/health/ready")
        assert set(response.json()["checks"]) == {"database"}
```

And in `services/backend/tests/api/test_config.py`:
- delete `"aws_endpoint_url": "",` from `_settings` (line 26);
- delete the whole `test_localstack_endpoint_is_refused_outside_local` method (lines 55–62);
- in `test_a_fully_configured_deployed_environment_is_valid`, replace `assert settings.aws_endpoint is None` with `assert not hasattr(settings, "aws_endpoint")`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd services/backend && uv run pytest tests/api/test_routes.py::TestHealth tests/api/test_config.py -q
```

Expected: readiness test fails with `{"database", "storage"} != {"database"}`; the `hasattr` assertion fails.

- [ ] **Step 3: Delete the adapters and the integration test**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
git rm -q services/backend/app/persistence/s3.py services/backend/app/persistence/dynamo.py tests/integration/test_s3.py
```

- [ ] **Step 4: Trim the health route**

In `services/backend/app/routes/health.py`: delete line 8 (`from app.persistence.s3 import check_storage`) and change line 31 to:

```python
    checks = {"database": await check_database()}
```

- [ ] **Step 5: Trim `app/config.py`**

Delete these lines:

```python
    aws_region: str = "us-west-2"
    aws_endpoint_url: str = ""
    s3_bucket: str = "ai-agent-saas-local"
    dynamodb_enabled: bool = False
    dynamodb_table: str = "ai-agent-saas-local"
```

Delete the `aws_endpoint` property (the four lines starting `@property` / `def aws_endpoint`). Delete this branch inside `_validate_environment`:

```python
            if self.aws_endpoint_url:
                raise ValueError(
                    "AWS_ENDPOINT_URL points the AWS SDK at a local emulator and "
                    f"must be empty when APP_ENV={self.app_env}."
                )
```

- [ ] **Step 6: Drop the dependencies and relock**

In `services/backend/pyproject.toml` delete line 27 (`"boto3>=1.42,<2.0",`) and line 49 (`"boto3-stubs[s3,dynamodb]>=1.42,<2.0",`). Then:

```bash
cd services/backend && uv lock && uv sync
```

Expected: `uv.lock` changes; boto3, botocore, s3transfer and the stubs disappear from it.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd services/backend && uv run pytest tests -q
```

Expected: all pass.

- [ ] **Step 8: Confirm nothing imports the deleted modules**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
grep -rn "persistence.s3\|persistence.dynamo\|boto3\|botocore\|s3_bucket\|aws_endpoint\|dynamodb" services packages evals tests --include='*.py' | grep -v "\.venv"
```

Expected: no output.

- [ ] **Step 9: `make check`, then commit**

```bash
make check
git add -A services/backend tests/integration
git commit -m "refactor(backend): remove the S3 and DynamoDB adapters

Only the readiness probe used them. The AWS path under advanced/ keeps its
own copies; the default path no longer needs an AWS SDK.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Remove the Bedrock provider

**Files:**
- Modify: `services/backend/agent_app/config.py:11,44-62`
- Modify: `services/backend/agent_app/interpreter.py:104-170,296-299`
- Modify: `services/backend/tests/agent/test_parse_and_replan.py:276-281,330-337,355,454-470`

**Interfaces:**
- Produces: `ModelProvider = Literal["anthropic", "scripted"]`. `ModelInterpreter._sampling()` always returns `{}`. `get_interpreter()` returns `ModelInterpreter` iff provider is `anthropic`.

- [ ] **Step 1: Update the tests first**

In `services/backend/tests/agent/test_parse_and_replan.py`:

Replace `test_bedrock_selects_the_bedrock_interpreter` (lines 276–281) with:

```python
    def test_an_unknown_provider_is_rejected_by_config(self) -> None:
        from pydantic import ValidationError

        from agent_app.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None, agent_model_provider="bedrock")  # type: ignore[arg-type,call-arg]
```

Rewrite the `TestNarration` docstring (lines 333–337) to:

```python
    """The model explains the plan; it never decides it.

    Regression guard: selecting a model provider used to change nothing about
    the reply — the composed text was always used, while a docstring claimed
    otherwise.
    """
```

Rename `test_the_model_writes_the_reply_when_bedrock_is_selected` (line 355) to `test_the_model_writes_the_reply_when_a_model_provider_is_selected`.

Replace `test_bedrock_sends_no_temperature_unless_configured` (lines 454–470) with:

```python
    def test_no_sampling_parameters_are_ever_sent(self) -> None:
        """Current Claude models 400 on temperature/top_p, and a failed call
        falls back to rules silently — so nothing is sent."""
        from agent_app.interpreter import ModelInterpreter

        assert ModelInterpreter()._sampling() == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd services/backend && uv run pytest tests/agent/test_parse_and_replan.py -q
```

Expected: `test_an_unknown_provider_is_rejected_by_config` fails (bedrock is still a valid literal).

- [ ] **Step 3: Trim `agent_app/config.py`**

Line 11: `ModelProvider = Literal["anthropic", "scripted"]`.

Delete the Bedrock block (the comment starting `# Bedrock through the Mantle` through `bedrock_temperature: float | None = None`).

Replace the provider comment so it reads:

```python
    # Which model interprets requests and writes replies:
    #   anthropic — Claude API directly
    #   scripted  — no model call; rule-based parsing and composed replies, so
    #               the reference app, E2E suite and deterministic evals run
    #               without credentials. Refused outside APP_ENV=local, for the
    #               same reason AUTH_DEV_FIXTURE is.
    agent_model_provider: ModelProvider = "anthropic"
```

- [ ] **Step 4: Trim `agent_app/interpreter.py`**

Replace the `ModelInterpreter` class header through `_sampling` (lines 104–169) with:

```python
class ModelInterpreter:
    """Claude via the Anthropic SDK.

    Structured output rather than free text plus parsing: the model fills a
    schema the rest of the system already validates, so a malformed answer fails
    at the boundary instead of becoming a strange itinerary.
    """

    def __init__(self) -> None:
        self.name: str = settings.agent_model_provider
        # The SDK's client is untyped at this boundary, so this is Any rather
        # than pretending to a precision the SDK does not provide.
        self._client: Any = None

    def _build_client(self) -> Any:
        """Construct the SDK client.

        Imported lazily so `AGENT_MODEL_PROVIDER=scripted` needs neither the
        SDK nor credentials.
        """
        from anthropic import AsyncAnthropic

        # Pass the key only when configured. The repository .env is read into
        # settings, not into the process environment, so the SDK would not
        # otherwise see it; when it is empty the SDK resolves credentials
        # itself.
        if settings.anthropic_api_key:
            return AsyncAnthropic(api_key=settings.anthropic_api_key)
        return AsyncAnthropic()

    @property
    def _model_id(self) -> str:
        return settings.anthropic_model_id

    @property
    def _max_tokens(self) -> int:
        return settings.anthropic_max_tokens

    def _sampling(self) -> dict[str, Any]:
        """Sampling parameters — deliberately none.

        Claude Opus 5 and Sonnet 5 reject `temperature`/`top_p`/`top_k` with a
        400, and `interpret` swallows a failed call as a fallback to rules — so
        sending one would quietly switch the model off rather than error.
        """
        return {}
```

Replace `get_interpreter` (lines 296–299) with:

```python
def get_interpreter() -> Interpreter:
    if settings.agent_model_provider == "anthropic":
        return ModelInterpreter()
    return RuleInterpreter()
```

Also update the module docstring at lines 10 and 14: remove `or Amazon Bedrock` and change `a Bedrock outage` to `a model outage`.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd services/backend && uv run pytest tests/agent -q && grep -rn -i bedrock agent_app app mcp_server tests
```

Expected: tests pass; grep prints nothing.

- [ ] **Step 6: `make check`, then commit**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template && make check
git add services/backend/agent_app services/backend/tests/agent
git commit -m "refactor(agent): remove the Bedrock provider

The Claude API is the one real provider on the default path; scripted stays
for tests. Bedrock was the last thing that needed AWS credentials.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: LocalStack out of compose, scripts, Makefile and `.env.example`

**Files:**
- Modify: `docker-compose.yml:3,29-47,62,80-83`
- Delete: `scripts/localstack/01-bootstrap.sh`
- Modify: `scripts/require-infra.sh:9`
- Modify: `Makefile:97-99,186-189`
- Modify: `.env.example:65-82,92-94,106-117,132-136`

**Interfaces:**
- Produces: `docker compose up` brings up `postgres`, `backend`, `web` only. `make infra-up` starts Postgres only.

- [ ] **Step 1: Edit `docker-compose.yml`**

Line 3: `#   make infra-up     → postgres only (recommended; run apps natively)`.

Delete the entire `localstack:` service block (lines 29–47).

In the `backend` service environment, replace the two `DATABASE_*` lines and the `AWS_ENDPOINT_URL` line with one line:

```yaml
      DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-app}
```

In the `backend` service `depends_on`, delete the `localstack:` / `condition: service_healthy` pair.

- [ ] **Step 2: Delete the LocalStack bootstrap and its check**

```bash
git rm -rq scripts/localstack
```

In `scripts/require-infra.sh` delete line 9 (the `localstack` check).

- [ ] **Step 3: Makefile**

Lines 97–99:

```make
infra-up: ## Start Postgres and apply migrations
	docker compose up -d postgres
```

Line 187: `test-integration: ## Integration tests against local Postgres + MCP`.

- [ ] **Step 4: `.env.example`**

Delete the `AWS — optional` block (the separator line above it through `DYNAMODB_TABLE=ai-agent-saas-local` and the blank line after).

Replace the two database lines and their comment with:

```bash
# One URL. The app derives the asyncpg and psycopg forms itself, so paste
# whatever your Postgres provider gives you.
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
```

Delete the `BEDROCK — optional` block (separator through `# BEDROCK_TEMPERATURE=` and the blank line after).

In the `MODEL PROVIDER` block delete the line `#   bedrock   — Claude on Amazon Bedrock (needs AWS credentials and model access)`.

- [ ] **Step 5: Verify the local stack**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
make infra-reset
make test-integration
docker compose up -d backend && sleep 15 && curl -sf http://localhost:8000/health/ready
docker compose down
grep -rn -i "localstack\|AWS_\|S3_BUCKET\|DYNAMODB\|BEDROCK\|DATABASE_SYNC_URL" docker-compose.yml scripts Makefile .env.example
```

Expected: integration tests pass against Postgres only; readiness returns `{"status":"ok",...,"checks":{"database":true}}`; the final grep prints nothing except the `advanced/` mentions in `scripts/smoke.sh` and `Makefile` (those are intentional pointers to the archived path).

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml scripts Makefile .env.example
git commit -m "chore(local): Postgres is the only local infrastructure

LocalStack leaves the default path with the adapters that used it. One
DATABASE_URL replaces the two driver-prefixed ones.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: CI without LocalStack or Terraform

**Files:**
- Modify: `.github/workflows/ci.yml` (terraform job; integration and e2e job services/env)

**Interfaces:**
- Consumes: plain `DATABASE_URL` from Task 1.

- [ ] **Step 1: Delete the `terraform` job**

Remove the whole block from the `# ----` separator above `terraform:` through the end of its `Validate every environment` step.

- [ ] **Step 2: Integration job**

Delete the `localstack:` service block under `services:`. In the job `env:`, delete `DATABASE_SYNC_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL`, `S3_BUCKET`, and change `DATABASE_URL` to:

```yaml
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/app
```

Rename the job: `name: Integration (Postgres + MCP)`.

- [ ] **Step 3: E2E job**

Delete `DATABASE_SYNC_URL` from its `env:` and change `DATABASE_URL` to the same plain form.

- [ ] **Step 4: Validate the YAML and inspect**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
ruby -ryaml -e 'YAML.load_file(".github/workflows/ci.yml"); puts "yaml ok"'
grep -n -i "localstack\|terraform\|AWS_\|S3_\|SYNC_URL" .github/workflows/ci.yml
```

Expected: `yaml ok` (macOS ships Ruby); grep prints nothing.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: drop LocalStack and the Terraform job from the default path

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `railway.json` replaces `fly.toml` and `render.yaml`

**Files:**
- Create: `railway.json`
- Delete: `fly.toml`, `render.yaml`
- Modify: `services/backend/Dockerfile:5-6,62-63`
- Modify: `Makefile:280-298` (deploy-help), `scripts/smoke.sh:6,27`

**Interfaces:**
- Produces: the Railway service definition. Pre-deploy command is `alembic upgrade head` run in the `runtime` image from `/app/services/backend`.

- [ ] **Step 1: Confirm the runtime image can run Alembic**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
docker build -f services/backend/Dockerfile -t backend-runtime-check .
docker run --rm backend-runtime-check sh -c "ls alembic.ini alembic/versions && alembic --version"
```

Expected: both files listed and an Alembic version printed. (The stage does `COPY services/backend/ ./` and `alembic` is a runtime dependency, so this should pass. If `alembic` is not on PATH, the venv is at `/app/services/backend/.venv/bin` and `ENV PATH` already includes it; investigate rather than adding a wrapper.)

- [ ] **Step 2: Create `railway.json`**

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "services/backend/Dockerfile"
  },
  "deploy": {
    "preDeployCommand": ["alembic", "upgrade", "head"],
    "healthcheckPath": "/health",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

- [ ] **Step 3: Delete the old host configs and fix references**

```bash
git rm -q fly.toml render.yaml
```

`services/backend/Dockerfile` lines 5–6: `#   runtime  — the deployed image (Railway, or anything that runs a container and speaks HTTP)`. Lines 62–63: `# \`$PORT\` when the platform assigns one (Railway does), 8000 otherwise.`

`Makefile` `deploy-help` target: replace its body with:

```make
	@echo "Deploys happen on push:"
	@echo "  dev      -> Railway env 'dev'        + Vercel preview"
	@echo "  staging  -> Railway env 'staging'    + Vercel preview"
	@echo "  main     -> Railway env 'production' + Vercel production"
	@echo ""
	@echo "Railway runs 'alembic upgrade head' before each deploy (railway.json)."
	@echo "See docs/DEPLOYMENT.md. AWS path: advanced/README.md"
```

And the comment block above it (starting `# Two deploys: the backend as a container`) becomes:

```make
# Railway deploys the backend and Vercel deploys the web app, both on branch
# push, so there is no deploy target here — see docs/DEPLOYMENT.md. The AWS path
# (Terraform, Lambda, AgentCore) is preserved under advanced/.
```

`scripts/smoke.sh` line 27: change `https://your-backend.fly.dev` to `https://your-backend.up.railway.app`.

- [ ] **Step 4: Check**

```bash
grep -rn -i "fly\.\|fly\.toml\|render\.yaml\|fly deploy" Makefile scripts services/backend/Dockerfile railway.json vercel.json
make check
```

Expected: grep prints nothing; check green.

- [ ] **Step 5: Commit**

```bash
git add railway.json services/backend/Dockerfile Makefile scripts/smoke.sh
git commit -m "feat(deploy): railway.json replaces fly.toml and render.yaml

Railway environments map one-to-one onto the dev, staging and main branches,
and its pre-deploy command runs migrations ahead of the code.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Rewrite `docs/DEPLOYMENT.md` and add ADR-010

**Files:**
- Rewrite: `docs/DEPLOYMENT.md`
- Create: `docs/adr/ADR-010-railway-and-vercel.md`
- Modify: `docs/adr/ADR-004-localstack-scope.md:3`

- [ ] **Step 1: Write `docs/DEPLOYMENT.md`**

Replace the whole file with:

````markdown
# Deployment

Three environments, three branches, two hosts. Push to a branch and its
environment deploys.

| Branch    | Backend (Railway environment) | Web (Vercel)             | `APP_ENV` |
|-----------|-------------------------------|--------------------------|-----------|
| `dev`     | `dev`                         | preview, branch `dev`    | `dev`     |
| `staging` | `staging`                     | preview, branch `staging`| `staging` |
| `main`    | `production`                  | Production               | `prod`    |

The backend — API, agent and MCP server, one ASGI application
([ADR-009](adr/ADR-009-one-backend-deployable.md)) — runs as one Railway
service per environment, with a Railway Postgres beside it. The web app is one
Vercel project. Nothing here needs an AWS account; that path lives under
[`advanced/`](../advanced/README.md).

## 1. Railway: first environment

1. **New Project → Deploy from GitHub repo**, pick this repository. Railway
   reads `railway.json` and builds `services/backend/Dockerfile` with the
   repository root as context. Name the service `backend`.
2. **+ New → Database → PostgreSQL** in the same environment.
3. On the `backend` service, **Variables**:

   | Variable            | Value                                   |
   |---------------------|-----------------------------------------|
   | `APP_ENV`           | `prod`                                  |
   | `DATABASE_URL`      | `${{Postgres.DATABASE_URL}}`            |
   | `MCP_ALLOWED_HOSTS` | `${{RAILWAY_PUBLIC_DOMAIN}}`            |
   | `API_CORS_ORIGINS`  | your production web URL                 |
   | `WORKOS_API_KEY`    | from WorkOS                             |
   | `WORKOS_CLIENT_ID`  | from WorkOS                             |
   | `ANTHROPIC_API_KEY` | secret                                  |

   `${{...}}` are Railway reference variables; only the last row is typed.
   `AGENT_MODEL_PROVIDER` defaults to `anthropic`.
4. **Settings → Networking → Generate Domain**. That hostname is what
   `MCP_ALLOWED_HOSTS` resolves to.
5. Rename the environment to `production` and confirm it tracks `main`
   (**Settings → Environment**).

Every deploy runs `alembic upgrade head` first (`preDeployCommand` in
`railway.json`), so the schema always leads the code that reads it. A failed
migration blocks the deploy; the previous version keeps serving.

## 2. Railway: staging and dev

**Environments → + New Environment → Duplicate `production`**, named
`staging`, tracking branch `staging`. Repeat for `dev`. Duplicating copies the
variables and provisions a fresh Postgres per environment; change `APP_ENV`
and `API_CORS_ORIGINS` in each copy. Secrets are shared by the copy — rotate
the Anthropic key per environment if you want separate spend tracking.

Then create the branches:

```bash
git checkout main && git pull
git branch dev && git branch staging
git push origin dev staging
```

## 3. Vercel

Connect the repository once; `vercel.json` carries the monorepo build wiring.
Production tracks `main`. Every other branch deploys as a preview; `dev` and
`staging` get stable aliases of the form
`<project>-git-<branch>-<team>.vercel.app`.

**Settings → Environment Variables.** Set the Production values, then add the
same names for Preview scoped to branch `staging`, and again scoped to `dev`:

| Variable                | Production            | Preview `staging`       | Preview `dev`           |
|-------------------------|-----------------------|-------------------------|-------------------------|
| `APP_ENV`               | `production`          | `staging`               | `dev`                   |
| `API_BASE_URL`          | production backend URL| staging backend URL     | dev backend URL         |
| `AGENT_BASE_URL`        | `<API_BASE_URL>/agent`| same pattern            | same pattern            |
| `NEXT_PUBLIC_APP_URL`   | production web URL    | staging branch alias    | dev branch alias        |
| `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_REDIRECT_URI`, `WORKOS_COOKIE_PASSWORD` | per WorkOS environment | per WorkOS environment | per WorkOS environment |

`NEXT_PUBLIC_*` variables are inlined at **build** time; changing one needs a
redeploy. `WORKOS_REDIRECT_URI` must exactly match what WorkOS has configured
for that environment: `<NEXT_PUBLIC_APP_URL>/auth/callback`.

## 4. Verify each environment

```bash
SMOKE_API_URL=https://<backend-host> SMOKE_WEB_URL=https://<web-host> make smoke ENV=staging
```

or by hand:

```bash
curl https://<backend-host>/health
curl https://<backend-host>/agent/ping
curl -i https://<backend-host>/mcp        # 400 = reachable; 421 = MCP_ALLOWED_HOSTS is wrong
```

Then point an MCP client at the deployed server and confirm the same tools your
chat UI uses are listed:

```json
{
  "mcpServers": {
    "plan-my-evening": { "url": "https://<backend-host>/mcp" }
  }
}
```

### `MCP_ALLOWED_HOSTS` is not optional

The MCP transport rejects any `Host` header it was not told to expect with a
421 — DNS-rebinding protection. `${{RAILWAY_PUBLIC_DOMAIN}}` keeps it correct;
if you add a custom domain, add it here too (comma-separated).

### Sleeping is the thing to watch

Railway's trial and hobby plans can sleep an idle service. A browser tolerates
the cold start; an MCP client such as Claude Desktop, which connects on its own
schedule, reads it as a broken server. If the MCP endpoint matters, keep the
service always-on (**Settings → App Sleeping** off).

## Order of operations

Migrations → backend → web, and Railway does the first two for you. The web app
reads `API_BASE_URL` at request time, so it can deploy against a backend that
is already up.

## Rollback

| Layer    | How |
|----------|-----|
| Web      | Vercel keeps every deployment — promote the previous one. |
| Backend  | Railway **Deployments → ⋯ → Redeploy** on the previous deployment. |
| Database | `alembic downgrade -1`, only when the migration is genuinely reversible. Prefer rolling forward. |

Because migrations run ahead of the code, rolling the backend back one release
is safe: the schema is a superset of what the older code expects.

## Promotion

`dev → staging → main` by pull request, as in
[GIT_WORKFLOW.md](GIT_WORKFLOW.md). CI runs evals and end-to-end tests on PRs
into `staging` and `main`. After a staging deploy:

```bash
SMOKE_API_URL=https://<staging-backend> NEXT_PUBLIC_APP_URL=https://<staging-web> make staging-check ENV=staging
```
````

- [ ] **Step 2: Write `docs/adr/ADR-010-railway-and-vercel.md`**

```markdown
# ADR-010: Railway and Vercel, three environments, no AWS on the default path

**Status:** Accepted — amends [ADR-009](ADR-009-one-backend-deployable.md); supersedes [ADR-004](ADR-004-localstack-scope.md) for the default path

## Context

ADR-009 collapsed the backend into one container and offered Fly or Render as
hosts. Neither models environments well: Fly needs one app and config per
environment, Render one blueprint entry per environment. The repository's git
workflow promises `dev → staging → main` with a deploy per branch, and nothing
implemented that.

The default path also still carried AWS: LocalStack in compose and CI, S3 and
DynamoDB adapters used only by the readiness probe, a Bedrock model provider,
and a Terraform CI job for code that had moved to `advanced/`.

## Decision

- **Railway hosts the backend.** Environments are first-class: `dev`,
  `staging` and `production` each hold the backend service and their own
  Postgres, and each tracks the branch of the same name. `railway.json` is the
  service definition; its pre-deploy command runs Alembic so the schema leads
  the code.
- **Vercel hosts the web app**, Production on `main`, previews with
  branch-scoped variables for `dev` and `staging`.
- **One `DATABASE_URL`.** The backend accepts a plain `postgresql://` URL and
  derives the asyncpg and psycopg forms. `DATABASE_SYNC_URL` is an optional
  override.
- **The AWS remnants leave the default path**: LocalStack, the S3 and DynamoDB
  adapters, the Bedrock provider, and the Terraform CI job. They are preserved
  under `advanced/` and in git history.

## Consequences

- A new environment is a dashboard duplicate plus one typed secret.
- No GitHub Actions deploy workflow. CI gates merges; the hosts deploy.
- The Anthropic API is the only real model provider on the default path.
- Object storage, when a product needs it, is a new decision — not a
  half-wired S3 adapter.
- `advanced/` is now further from the default path; anyone graduating to it
  restores the adapters from history rather than flipping a flag.
```

- [ ] **Step 3: Mark ADR-004**

`docs/adr/ADR-004-localstack-scope.md` line 3: `**Status:** Superseded for the default path by [ADR-010](ADR-010-railway-and-vercel.md); still applies under `advanced/``.

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOYMENT.md docs/adr/ADR-010-railway-and-vercel.md docs/adr/ADR-004-localstack-scope.md
git commit -m "docs: deployment guide for Railway + Vercel across three environments

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Remaining docs and README

**Files:**
- Modify: `docs/DEVELOPMENT.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/TEMPLATE_CHECKLIST.md`, `docs/GIT_WORKFLOW.md`, `README.md`, `advanced/README.md`

Line numbers below are as of the start of the task; edit top-down in each file or use the quoted text to locate.

- [ ] **Step 1: `docs/DEVELOPMENT.md`**

- Line 11: delete `AWS local emulator       LocalStack`.
- Lines 34–35: `Variables are grouped by concern in \`.env.example\`: APP, WORKOS, DATABASE, AGENT, ANTHROPIC, MODEL PROVIDER, MCP, MAPS, and the event/place providers.`
- Line 43: `| \`AGENT_MODEL_PROVIDER\` | \`anthropic\` or \`scripted\`. \`scripted\` skips model inference; refused unless \`APP_ENV=local\`. |`
- Line 45: delete the `AWS_ENDPOINT_URL` row.
- Line 46: `| \`DATABASE_URL\` | Plain \`postgresql://\`; the app derives asyncpg and psycopg forms. \`DATABASE_SYNC_URL\` optionally overrides the sync one. |`
- Lines 96–100: the code block becomes just `postgres`.
- Line 105: `docker compose up -d postgres`.
- Lines 132–150: delete the whole `# LocalStack` section (heading through the `lstk terraform` block and its closing fence, up to the next `---`). Replace it with:

  ```markdown
  # AWS emulation

  The default path uses no AWS services. The `advanced/` Terraform path still
  validates against LocalStack; see [advanced/README.md](../advanced/README.md).
  ```
- Line 186: delete the `bedrock` row.
- Line 344: `Postgres in a container, and \`make dev\` runs the application`.
- Lines 369–370: `Migrations use the synchronous driver while the application uses asyncpg; both derive from \`DATABASE_URL\`, so deploy tooling never needs an event loop.`

- [ ] **Step 2: `docs/ARCHITECTURE.md`**

- Lines 119–121: `It calls Claude through the Anthropic SDK. Swapping the model is a configuration change (\`ANTHROPIC_MODEL_ID\`), not a code change.`
- Line 294: `Claude (Claude API)`.
- Lines 390–392: delete `- S3,` and `- optional DynamoDB,`.
- Line 406: delete `AWS primitives   → LocalStack where useful`.
- Line 412: `Backend (all three)  → one container per environment on Railway`.
- Line 413: `Postgres             → Railway Postgres (one per environment)`.
- Line 414: delete `S3                   → AWS S3`.

- [ ] **Step 3: `docs/TESTING.md`**

- Line 171: delete the `test_s3.py` row.
- Lines 263–267: delete `Optionally apply relevant modules to LocalStack:` and its code block.
- Search the file for `LocalStack` and `make test-integration` descriptions; any remaining "Postgres + LocalStack" becomes "Postgres".

- [ ] **Step 4: `docs/TEMPLATE_CHECKLIST.md`**

- Line 83: `services/backend/app/persistence/                 engine, session`.
- Line 141: `- [ ] confirm Postgres fits the access patterns`.
- Line 145: `- [ ] add object storage if blobs/files are required (not included by default)`.
- Line 153: delete `- [ ] LocalStack if useful`.

- [ ] **Step 5: `docs/GIT_WORKFLOW.md`**

Under `### main` rules add `- deploys to Railway \`production\` and Vercel Production on push.` Under `### staging` change `deploys automatically to staging` to `deploys to Railway \`staging\` and a Vercel preview on push`. Under `### dev` change `automatically deployable to shared dev` to `deploys to Railway \`dev\` and a Vercel preview on push`.

- [ ] **Step 6: `README.md`**

- Line 11: `- **Anthropic SDK** for model calls against the Claude API`.
- Line 14: `- **Postgres** for application persistence`.
- Line 15: `- **Docker Compose** for fast local development`.
- Line 16: `- **Vercel + Railway** for deployment across dev, staging and production; Terraform/AWS under \`advanced/\``.
- Lines 85–86 (diagram): `│ Postgres             │` and a line of spaces matching the box width in place of the DynamoDB line.
- Line 139: `│   ├── integration/             # against real Postgres and MCP`.
- Line 145: `├── railway.json                 # backend hosting`.
- Line 161: `│   ├── persistence/           postgres.py`.
- Line 260: `Postgres`.
- Line 322: delete the `S3 / DynamoDB` row. Line 328: delete the "Do **not** force LocalStack…" paragraph.
- Lines 362 and 366: `| Docker | Postgres | yes |` and delete the duplicate Docker row (keep one).
- Line 391: `- \`AGENT_MODEL_PROVIDER=scripted\` skips model inference and parses requests`.
- Line 398: `To use the real services, set \`WORKOS_*\`, \`AGENT_MODEL_PROVIDER=anthropic\`, \`ANTHROPIC_API_KEY\` and the`.
- Line 424: `make test-integration   # against real Postgres and MCP`.
- Lines 433–445 (Deployment section): replace with:

  ````markdown
  ## Deployment

  Push to a branch and its environment deploys. Full guide:
  [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

  | Branch    | Backend                    | Web                |
  |-----------|----------------------------|--------------------|
  | `dev`     | Railway env `dev`          | Vercel preview     |
  | `staging` | Railway env `staging`      | Vercel preview     |
  | `main`    | Railway env `production`   | Vercel production  |

  Railway runs `alembic upgrade head` before each deploy, so the schema always
  leads the code.
  ````
- Line 512: `- [ADR-004 — LocalStack, used selectively](docs/adr/ADR-004-localstack-scope.md) *(default path: superseded by ADR-010)*`. Add after the ADR-009 line: `- [ADR-010 — Railway and Vercel, three environments](docs/adr/ADR-010-railway-and-vercel.md)`.
- Line 537: delete `- [x] S3 object storage with tenant-prefixed keys`.
- Line 542: `- [x] Agent on the Anthropic SDK against the Claude API`.
- Line 559: delete `- [x] LocalStack for the AWS services it reproduces well`.

- [ ] **Step 7: `advanced/README.md`**

In the table, change the `Backend` default cell to `One container per environment on Railway`, `Database` default to `Railway Postgres`, `Environments` default to `` `dev`, `staging`, `production` ``. After the table add:

```markdown
The default path no longer ships the S3/DynamoDB adapters, the Bedrock model
provider or LocalStack ([ADR-010](../docs/adr/ADR-010-railway-and-vercel.md)).
They are still in git history: check out the commit before ADR-010 landed
(`git log --diff-filter=D -- services/backend/app/persistence/s3.py` finds it)
if you graduate to this path and need them.
```

- [ ] **Step 8: Sweep**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
grep -rn -i "localstack\|dynamo\|\bs3\b\|bedrock\|fly\.io\|fly\.toml\|render\.yaml\|DATABASE_SYNC_URL\|neon" \
  --exclude-dir=advanced --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git \
  --exclude-dir=superpowers . | grep -v "docs/adr/"
```

Expected: only intentional pointers remain — `scripts/smoke.sh` and `Makefile` mentioning the `advanced/` path, `DATABASE_SYNC_URL` in `app/config.py`, `alembic/env.py`, the db_url test and `docs/DEVELOPMENT.md` as the documented override. Anything else gets fixed before committing.

- [ ] **Step 9: Commit**

```bash
git add README.md docs advanced/README.md
git commit -m "docs: remove Fly, Render, LocalStack, S3, DynamoDB and Bedrock from the default path

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Final verification

- [ ] **Step 1: Everything green from a clean state**

```bash
cd /Users/blakedanson/repos/ai-agent-saas-template
make check
make infra-reset && make test-integration
docker compose build backend
```

Expected: all green; image builds without boto3.

- [ ] **Step 2: Spec checklist**

Confirm against the spec's Verification section:

```bash
grep -rn "boto3\|localstack\|bedrock\|fly.io\|render.yaml" --exclude-dir=advanced --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git . | grep -v "docs/adr/\|docs/superpowers/"
```

Expected: no output.

- [ ] **Step 3: Push and hand off**

```bash
git push -u origin simplify/railway-three-envs
```

Then report to the user: the branch is pushed; the dashboard checklist is sections 1–3 of `docs/DEPLOYMENT.md`; the `dev` and `staging` branches should be created after this merges.
