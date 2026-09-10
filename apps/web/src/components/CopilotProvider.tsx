"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import type { ReactNode } from "react";

/**
 * CopilotKit provider.
 *
 * `runtimeUrl` points at this app's own server route, which is where the
 * session's access token is attached before the request reaches the agent. No
 * credential is exposed to the browser.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  return <CopilotKitProvider runtimeUrl="/api/copilotkit">{children}</CopilotKitProvider>;
}

export default CopilotProvider;
