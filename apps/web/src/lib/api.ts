import "server-only";

import type { PlanCreate, PlanList, PlanRead } from "@saas/contracts";

import { getSession, type Session } from "./auth";
import { serverEnv } from "./env";

/**
 * Server-side client for the deterministic application API.
 *
 * Runs only on the server, because it forwards the session's access token. The
 * browser never holds that token and never calls the API directly.
 */

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, session: Session, init: RequestInit = {}): Promise<T> {
  const { apiBaseUrl } = serverEnv();

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let code = "api_error";
    let message = response.statusText;
    try {
      const body = await response.json();
      code = body.code ?? code;
      message = body.message ?? message;
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new ApiError(code, message, response.status);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export async function listPlans(): Promise<PlanList> {
  const session = await getSession();
  if (!session) return { items: [], total: 0 };
  return request<PlanList>("/plans", session);
}

export async function getPlan(planId: string): Promise<PlanRead> {
  const session = await getSession();
  if (!session) throw new ApiError("not_authenticated", "Not signed in.", 401);
  return request<PlanRead>(`/plans/${planId}`, session);
}

export async function createPlan(payload: PlanCreate): Promise<PlanRead> {
  const session = await getSession();
  if (!session) throw new ApiError("not_authenticated", "Not signed in.", 401);
  return request<PlanRead>("/plans", session, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function apiHealthy(): Promise<boolean> {
  try {
    const { apiBaseUrl } = serverEnv();
    const response = await fetch(`${apiBaseUrl}/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}
