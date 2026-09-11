import { AppShell } from "@/components/AppShell";
import { isDevFixtureAuth, requireSession } from "@/lib/auth";

// Pages here depend on the current session, so none can be prerendered.
// Without this the fixture identity would be baked into a static build.
export const dynamic = "force-dynamic";

/**
 * Map pages: the content owns the whole viewport below the app bar.
 *
 * No gutters and no scrolling — the map fills the space and the itinerary
 * floats over it.
 *
 * Separate from (standard) because a layout cannot vary a prop per child
 * route, and this is the only difference between them. This layout is also
 * the authentication boundary for the routes beneath it.
 */
export default async function MapLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();

  return (
    <AppShell session={session} devFixtureAuth={isDevFixtureAuth} fullBleed>
      {children}
    </AppShell>
  );
}
