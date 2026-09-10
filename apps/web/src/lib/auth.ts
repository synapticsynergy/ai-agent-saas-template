import "server-only";

import { withAuth } from "@workos-inc/authkit-nextjs";

import { AUTH_DEV_FIXTURE, AUTH_DEV_FIXTURE_TOKEN, IS_LOCAL } from "./env";

/**
 * Server-side session access.
 *
 * A `Session` is the trusted identity context: it comes from a verified WorkOS
 * session, and it is what the app forwards to the API and the agent. Nothing in
 * the browser and nothing a model produces can influence it.
 */
export interface Session {
  userId: string;
  organizationId: string;
  email: string;
  role: string;
  permissions: string[];
  /** Forwarded as a bearer token so every downstream hop can verify it. */
  accessToken: string;
}

const FIXTURE_ROLE_PERMISSIONS: Record<string, string[]> = {
  viewer: ["plans:read", "preferences:read"],
  member: ["plans:read", "plans:write", "agents:run", "preferences:read", "preferences:write"],
  admin: [
    "plans:read",
    "plans:write",
    "plans:delete",
    "agents:run",
    "preferences:read",
    "preferences:write",
    "org:manage",
  ],
};

function fixtureSession(): Session {
  const role = process.env.AUTH_DEV_FIXTURE_ROLE ?? "member";
  return {
    userId: process.env.AUTH_DEV_FIXTURE_USER_ID ?? "user_local_demo",
    organizationId: process.env.AUTH_DEV_FIXTURE_ORG_ID ?? "org_local_demo",
    email: process.env.AUTH_DEV_FIXTURE_EMAIL ?? "demo@example.com",
    role,
    permissions: FIXTURE_ROLE_PERMISSIONS[role] ?? [],
    accessToken: AUTH_DEV_FIXTURE_TOKEN,
  };
}

/** The current session, or null when nobody is signed in. */
export async function getSession(): Promise<Session | null> {
  if (AUTH_DEV_FIXTURE) {
    return fixtureSession();
  }

  const { user, organizationId, role, permissions, accessToken } = await withAuth();
  if (!user || !accessToken) return null;

  if (!organizationId) {
    // The template is organization-scoped throughout. A session with no
    // organization cannot address any tenant data, so treat it as signed out
    // rather than letting a null tenant flow downstream.
    return null;
  }

  return {
    userId: user.id,
    organizationId,
    email: user.email ?? "",
    role: role ?? "",
    permissions: permissions ?? [],
    accessToken,
  };
}

/** The current session, or a redirect to sign-in. */
export async function requireSession(): Promise<Session> {
  const session = await getSession();
  if (session) return session;

  if (AUTH_DEV_FIXTURE) {
    // Unreachable: getSession() always returns a session in fixture mode.
    return fixtureSession();
  }

  const { redirect } = await import("next/navigation");
  const { getSignInUrl } = await import("@workos-inc/authkit-nextjs");
  // `redirect` throws; it never returns.
  redirect(await getSignInUrl());
  throw new Error("unreachable");
}

export function hasPermission(session: Session, permission: string): boolean {
  return session.permissions.includes(permission);
}

/**
 * Permission check for server code.
 *
 * The UI uses `hasPermission` to decide what to *offer*. That is a usability
 * choice, not a security control — the API enforces the same permission on
 * every request regardless of what the UI rendered.
 */
export function requirePermission(session: Session, permission: string): void {
  if (!hasPermission(session, permission)) {
    throw new Error(`Missing required permission: ${permission}`);
  }
}

export const isDevFixtureAuth = AUTH_DEV_FIXTURE && IS_LOCAL;
