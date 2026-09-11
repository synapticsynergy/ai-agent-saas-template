import { AppShell } from "@/components/AppShell";
import { isDevFixtureAuth, requireSession } from "@/lib/auth";

// Pages here depend on the current session, so none can be prerendered.
// Without this the fixture identity would be baked into a static build.
export const dynamic = "force-dynamic";

/**
 * Normal pages: a padded, max-width container inside the app shell.
 *
 * This layout is the authentication boundary for the routes beneath it —
 * `requireSession()` runs before any of them render, so no page has to
 * remember to check. The API enforces the same identity independently on
 * every request.
 */
export default async function StandardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();

  return (
    <AppShell session={session} devFixtureAuth={isDevFixtureAuth}>
      {children}
    </AppShell>
  );
}
