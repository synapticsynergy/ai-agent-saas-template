# syntax=docker/dockerfile:1
#
# Build context is the repository root: the agent depends on
# packages/contracts as a path dependency.
#
#   dev        — hot-reloading local container (docker compose)
#   agentcore  — AgentCore Runtime container
#
# AgentCore Runtime requires linux/arm64 and expects the container to serve
# POST /invocations and GET /ping on port 8080. Build the runtime image with:
#   docker build --platform linux/arm64 -f services/agent/Dockerfile \
#     --target agentcore -t <repo>:<tag> .

# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY packages/contracts /packages/contracts
COPY services/agent/pyproject.toml services/agent/uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev 2>/dev/null \
    || uv sync --no-install-project --no-dev

COPY services/agent/ ./

ENV PATH="/app/.venv/bin:$PATH"

# ---------------------------------------------------------------------------
FROM base AS dev

EXPOSE 8080
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

# ---------------------------------------------------------------------------
FROM base AS agentcore

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8080/ping')"]
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
