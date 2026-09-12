# syntax=docker/dockerfile:1
#
# Build context is the repository root.
#
#   dev      — hot-reloading local container (docker compose)
#   runtime  — the deployed image (Railway, or anything that runs a container
#              and speaks HTTP)
#
# One image serves the API, the agent and the MCP server, because they are one
# ASGI application (ADR-009). There is no Lambda target: the agent streams SSE,
# which wants a long-lived connection rather than an invocation.
#
# The image mirrors the repository layout (/app/services/backend alongside
# /app/packages/contracts) because the service declares contracts as a
# `../../packages/contracts` path dependency; flattening the service to /app
# would make that path resolve above the container root.

# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/services/backend

# Dependency layer first: application edits do not invalidate the install.
COPY packages/contracts /app/packages/contracts
COPY services/backend/pyproject.toml services/backend/uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY services/backend/ ./

ENV PATH="/app/services/backend/.venv/bin:$PATH"

# ---------------------------------------------------------------------------
FROM base AS dev

RUN --mount=type=cache,target=/root/.cache/uv uv sync
EXPOSE 8000
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
FROM base AS test

RUN --mount=type=cache,target=/root/.cache/uv uv sync
CMD ["pytest", "tests", "-q"]

# ---------------------------------------------------------------------------
FROM base AS runtime

# Drop privileges: nothing here needs root at runtime.
RUN useradd --create-home --uid 10001 app \
 && chown -R app:app /app
USER app

EXPOSE 8000

# `$PORT` when the platform assigns one (Railway does), 8000 otherwise. Exec
# form cannot expand variables, so this goes through a shell.
CMD ["sh", "-c", "exec uvicorn asgi:app --host 0.0.0.0 --port ${PORT:-8000}"]
