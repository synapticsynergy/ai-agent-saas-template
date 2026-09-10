# syntax=docker/dockerfile:1
#
# Build context is the repository root: the MCP server depends on
# packages/contracts as a path dependency.
#   dev     — hot-reloading local container
#   lambda  — AWS Lambda container image behind a Function URL

# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY packages/contracts /packages/contracts
COPY services/mcp/pyproject.toml services/mcp/uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

COPY services/mcp/ ./

# ---------------------------------------------------------------------------
FROM base AS dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8090
CMD ["python", "server.py"]

# ---------------------------------------------------------------------------
FROM base AS requirements

RUN uv export --no-dev --no-hashes --no-emit-project --format requirements.txt \
    > /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Lambda container image. The MCP server is stateless HTTP, so it fits a Lambda
# Function URL; set stateless_http when session affinity is not available.
FROM public.ecr.aws/lambda/python:3.12 AS lambda

COPY --from=requirements /tmp/requirements.txt /tmp/requirements.txt
COPY packages/contracts /tmp/contracts

RUN pip install --no-cache-dir --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt \
 && pip install --no-cache-dir --target "${LAMBDA_TASK_ROOT}" /tmp/contracts

COPY services/mcp/mcp_server "${LAMBDA_TASK_ROOT}/mcp_server"
COPY services/mcp/lambda_handler.py "${LAMBDA_TASK_ROOT}/"

CMD ["lambda_handler.handler"]
