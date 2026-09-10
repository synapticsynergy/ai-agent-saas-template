import { authkitMiddleware } from "@workos-inc/authkit-nextjs";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { AUTH_DEV_FIXTURE } from "@/lib/env";

/**
 * AuthKit session middleware.
 *
 * `withAuth()` only works on paths this middleware covers, so it must run
 * everywhere the app reads a session.
 *
 * When the local fixture identity is active there is no WorkOS session to
 * refresh, so the middleware steps aside entirely. `AUTH_DEV_FIXTURE` is false
 * unless `APP_ENV=local` (see lib/env.ts), and both the web app and the API
 * refuse to start with the flag set outside local — so this branch cannot be
 * reached in a deployed environment.
 */
const workosMiddleware = authkitMiddleware({
  middlewareAuth: {
    enabled: true,
    unauthenticatedPaths: ["/", "/login", "/auth/callback"],
  },
});

export default function middleware(request: NextRequest) {
  if (AUTH_DEV_FIXTURE) {
    return NextResponse.next();
  }
  return workosMiddleware(request, {} as never);
}

export const config = {
  matcher: [
    // Everything except Next internals and static assets.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
