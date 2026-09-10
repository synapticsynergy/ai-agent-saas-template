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
 * traffic goes browser → here → AgentCore Runtime → Strands → MCP. Ordinary
 * application traffic goes browser → Next.js server → FastAPI. Keeping the two
 * apart is ADR-001.
 *
 * Agents are resolved per request (`agents` as a factory) rather than once at
 * module load, because the token differs for every user and must never be
 * captured in a shared, long-lived agent instance.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BASE_PATH = "/api/copilotkit";

const copilotRuntime = new CopilotRuntime({
  agents: async () => {
    const session = await getSession();
    if (!session) {
      throw new Error("Not authenticated.");
    }

    const { agentBaseUrl } = serverEnv();

    return {
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
  return handler(request);
}

export const GET = guard;
export const POST = guard;
