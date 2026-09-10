import { getSignInUrl } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";

import { AUTH_DEV_FIXTURE } from "@/lib/env";

/** Start the WorkOS AuthKit sign-in flow. */
export async function GET() {
  if (AUTH_DEV_FIXTURE) {
    // The fixture identity is always signed in; there is nothing to authorize.
    redirect("/planner");
  }
  redirect(await getSignInUrl());
}
