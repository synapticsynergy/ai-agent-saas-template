/**
 * Environment access with startup validation.
 *
 * Server-side configuration is read through `serverEnv()`, which throws a
 * readable error naming every missing variable rather than surfacing
 * `undefined` deep inside a request handler.
 */

export type AppEnv = "local" | "dev" | "staging" | "prod";

export const APP_ENV = (process.env.APP_ENV ?? "local") as AppEnv;
export const IS_LOCAL = APP_ENV === "local";

/**
 * Local-only fixture identity. Enabled only when `AUTH_DEV_FIXTURE=1` *and*
 * `APP_ENV=local`; `serverEnv()` throws if the two disagree, so it cannot be
 * switched on by accident in a deployed environment.
 */
export const AUTH_DEV_FIXTURE = process.env.AUTH_DEV_FIXTURE === "1" && IS_LOCAL;
export const AUTH_DEV_FIXTURE_TOKEN =
  process.env.AUTH_DEV_FIXTURE_TOKEN ?? "local-dev-fixture-token";

export interface ServerEnv {
  appEnv: AppEnv;
  apiBaseUrl: string;
  agentBaseUrl: string;
  workosClientId: string;
  workosApiKey: string;
  workosRedirectUri: string;
}

let cached: ServerEnv | null = null;

export function serverEnv(): ServerEnv {
  if (cached) return cached;

  if (process.env.AUTH_DEV_FIXTURE === "1" && !IS_LOCAL) {
    throw new Error(
      `AUTH_DEV_FIXTURE is enabled but APP_ENV is "${APP_ENV}". The fixture ` +
        "identity is a local-development aid and must never be reachable in a " +
        "deployed environment.",
    );
  }

  const env: ServerEnv = {
    appEnv: APP_ENV,
    apiBaseUrl: process.env.API_BASE_URL ?? "http://localhost:8000",
    agentBaseUrl: process.env.AGENT_BASE_URL ?? "http://localhost:8080",
    workosClientId: process.env.WORKOS_CLIENT_ID ?? "",
    workosApiKey: process.env.WORKOS_API_KEY ?? "",
    workosRedirectUri: process.env.WORKOS_REDIRECT_URI ?? "",
  };

  // Real WorkOS configuration is required unless the local fixture is active.
  if (!AUTH_DEV_FIXTURE) {
    const missing = (
      [
        ["WORKOS_CLIENT_ID", env.workosClientId],
        ["WORKOS_API_KEY", env.workosApiKey],
        ["WORKOS_REDIRECT_URI", env.workosRedirectUri],
        ["WORKOS_COOKIE_PASSWORD", process.env.WORKOS_COOKIE_PASSWORD ?? ""],
      ] as const
    )
      .filter(([, value]) => !value)
      .map(([name]) => name);

    if (missing.length > 0) {
      throw new Error(
        `Missing WorkOS configuration: ${missing.join(", ")}.\n\n` +
          "Create a WorkOS development environment at https://dashboard.workos.com " +
          "and set these in .env — see docs/DEVELOPMENT.md.\n\n" +
          "For local development without WorkOS, set APP_ENV=local and " +
          "AUTH_DEV_FIXTURE=1 to use the isolated fixture identity instead.",
      );
    }
  }

  cached = env;
  return env;
}

/** Public (client-visible) configuration. Never put a secret here. */
export const publicEnv = {
  appUrl: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  mapStyleUrl: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://demotiles.maplibre.org/style.json",
} as const;
