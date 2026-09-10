import { handleAuth } from "@workos-inc/authkit-nextjs";

/**
 * WorkOS AuthKit redirect URI.
 *
 * Must match `WORKOS_REDIRECT_URI` and the redirect configured in the WorkOS
 * dashboard, or sign-in fails with a redirect mismatch.
 */
export const GET = handleAuth({ returnPathname: "/planner" });
