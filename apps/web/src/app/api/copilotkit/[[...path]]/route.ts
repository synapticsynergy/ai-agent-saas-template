import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

import { getSession } from "@/lib/auth";
import { serverEnv } from "@/lib/env";

/**
 * CopilotKit runtime endpoint.
 *
 * This route is the **identity injection boundary**. It runs on the server,
 * reads the verified WorkOS session, and attaches that session's access token
 * to the request it makes to the agent runtime. The browser never holds the
 * token, and the agent never has to trust a client-supplied identity.
 *
 * Note what this route is *not*: a proxy for the deterministic API. Agent
 * traffic goes browser → here → the agent → MCP. Ordinary application traffic
 * goes browser → Next.js server → the API. Those are still two separate paths
 * with different shapes, even though the backend now serves both from one
 * process (ADR-009) — this route never carries CRUD.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BASE_PATH = "/api/copilotkit";

/**
 * Conversation-thread endpoints, blocked deliberately.
 *
 * The SSE runtime's default runner keeps threads in a process-global in-memory
 * store with no tenant scoping — `/threads` returns every thread the process
 * has seen, to any caller. That is a tenant boundary this template will not
 * cross (see docs/adr/ADR-008).
 *
 * Nothing here needs them: the itinerary travels as AG-UI state and a saved
 * plan is a row in Postgres, retrievable through the deterministic API. If a
 * downstream product wants durable, resumable conversations, give the runtime a
 * tenant-scoped `runner` backed by real storage and unblock these paths then.
 */
const BLOCKED_PATHS = ["/threads"];

const copilotRuntime = new CopilotRuntime({
  agents: async () => {
    const session = await getSession();
    if (!session) {
      throw new Error("Not authenticated.");
    }

    const { agentBaseUrl } = serverEnv();

    return {
      // Built per request, never module-scope: the token differs for every
      // user and must not be captured in a shared, long-lived instance.
      planner: new HttpAgent({
        url: `${agentBaseUrl}/invocations`,
        headers: {
          // The assertion the agent forwards to MCP, and MCP forwards to the
          // API. Each hop verifies it independently.
          Authorization: `Bearer ${session.accessToken}`,
        },
      }),
    };
  },
});

const handler = createCopilotRuntimeHandler({
  runtime: copilotRuntime,
  basePath: BASE_PATH,
});

async function guard(request: Request): Promise<Response> {
  const session = await getSession();
  if (!session) {
    return Response.json(
      { code: "not_authenticated", message: "Sign in to use the assistant." },
      { status: 401 },
    );
  }

  const path = new URL(request.url).pathname.slice(BASE_PATH.length);
  if (BLOCKED_PATHS.some((blocked) => path.startsWith(blocked))) {
    return Response.json(
      {
        code: "not_found",
        message:
          "Conversation-thread endpoints are disabled. Saved plans are available " +
          "from the application API.",
      },
      { status: 404 },
    );
  }

  return handler(request);
}

export const GET = guard;
export const POST = guard;
