# syntax=docker/dockerfile:1
#
# Build context is the repository root.
#
#   dev     — hot-reloading local container (docker compose)
#   lambda  — AWS Lambda container image (production target)
#
# The image mirrors the repository layout (/app/services/api alongside
# /app/packages/contracts) because the service declares contracts as a
# `../../packages/contracts` path dependency; flattening the service to /app
# would make that path resolve above the container root.

# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/services/api

# Dependency layer first: application edits do not invalidate the install.
COPY packages/contracts /app/packages/contracts
COPY services/api/pyproject.toml services/api/uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project

COPY services/api/ ./

ENV PATH="/app/services/api/.venv/bin:$PATH"

# ---------------------------------------------------------------------------
FROM base AS dev

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
FROM base AS test

RUN --mount=type=cache,target=/root/.cache/uv uv sync
CMD ["pytest", "tests", "-q"]

# ---------------------------------------------------------------------------
# Export a pinned requirements file so the Lambda image installs exactly the
# same resolved versions as local development.
FROM base AS requirements

RUN uv export --no-dev --no-hashes --no-emit-project --format requirements.txt \
    | grep -v '^-e ' > /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Lambda container image. Mangum adapts the ASGI app to the Lambda event shape;
# API Gateway (HTTP API) sits in front. See infra/terraform/modules/api.
FROM public.ecr.aws/lambda/python:3.12 AS lambda

COPY --from=requirements /tmp/requirements.txt /tmp/requirements.txt
COPY packages/contracts /tmp/contracts

# Install into the Lambda task root rather than a virtualenv: the Lambda
# runtime imports from there directly.
RUN pip install --no-cache-dir --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt \
 && pip install --no-cache-dir --target "${LAMBDA_TASK_ROOT}" /tmp/contracts

COPY services/api/app "${LAMBDA_TASK_ROOT}/app"
COPY services/api/alembic "${LAMBDA_TASK_ROOT}/alembic"
COPY services/api/alembic.ini "${LAMBDA_TASK_ROOT}/"

CMD ["app.main.handler"]
