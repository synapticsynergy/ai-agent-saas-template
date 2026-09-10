# syntax=docker/dockerfile:1
#
# Build context is the repository root: the web app depends on the
# packages/contracts workspace package.
#
#   dev      — hot-reloading local container (docker compose)
#   runtime  — standalone production server

# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS base

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

WORKDIR /app

# Dependency layer first: application edits do not invalidate the install.
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json ./apps/web/
COPY packages/contracts/package.json ./packages/contracts/

RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

COPY packages/contracts ./packages/contracts
COPY apps/web ./apps/web

# ---------------------------------------------------------------------------
FROM base AS dev

WORKDIR /app/apps/web
EXPOSE 3000
CMD ["pnpm", "dev"]

# ---------------------------------------------------------------------------
FROM base AS build

ENV NEXT_OUTPUT_STANDALONE=1
# Next inlines NEXT_PUBLIC_* at build time, so they must be present here.
ARG NEXT_PUBLIC_APP_URL
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_MAP_STYLE_URL

RUN pnpm --filter web build

# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

WORKDIR /app

# Next's standalone output bundles only the files the server actually needs.
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /app/apps/web/public ./apps/web/public

USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
