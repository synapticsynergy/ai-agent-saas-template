import { signOut } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";

import { AUTH_DEV_FIXTURE } from "@/lib/env";

/** End the session and return to the marketing page. */
export async function GET() {
  if (AUTH_DEV_FIXTURE) {
    redirect("/");
  }
  await signOut({ returnTo: "/" });
}
