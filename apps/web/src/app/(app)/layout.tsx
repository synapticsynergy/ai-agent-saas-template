import { AppShell } from "@/components/AppShell";
import { isDevFixtureAuth, requireSession } from "@/lib/auth";

/**
 * Protected route group.
 *
 * Every page under `(app)` inherits this layout, so authentication is enforced
 * by placement rather than by each page remembering to check. The API enforces
 * the same identity independently on every request.
 */
// Every page in this group depends on the current session, so none of them can
// be prerendered. Without this the fixture identity would be baked into a
// static build.
export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();

  return (
    <AppShell session={session} devFixtureAuth={isDevFixtureAuth}>
      {children}
    </AppShell>
  );
}
