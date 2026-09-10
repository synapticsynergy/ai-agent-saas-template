"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import type { ReactNode } from "react";

/**
 * CopilotKit provider.
 *
 * `runtimeUrl` points at this app's own server route, which is where the
 * session's access token is attached before the request reaches the agent. No
 * credential is exposed to the browser.
 *
 * The inspector is off. It is a useful debugging surface, but it renders a
 * "View in Inspector" row for every tool call inside the conversation, which
 * buries the assistant's actual reply. Set `NEXT_PUBLIC_COPILOTKIT_INSPECTOR=1`
 * when you want it back.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      enableInspector={process.env.NEXT_PUBLIC_COPILOTKIT_INSPECTOR === "1"}
    >
      {children}
    </CopilotKitProvider>
  );
}

export default CopilotProvider;
