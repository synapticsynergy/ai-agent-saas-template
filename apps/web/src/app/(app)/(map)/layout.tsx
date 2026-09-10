import { AppShell } from "@/components/AppShell";
import { isDevFixtureAuth, requireSession } from "@/lib/auth";

/**
 * Map pages: the content owns the whole viewport below the app bar.
 *
 * No gutters and no scrolling — the map fills the space and the itinerary
 * floats over it.
 */
export default async function MapLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();

  return (
    <AppShell session={session} devFixtureAuth={isDevFixtureAuth} fullBleed>
      {children}
    </AppShell>
  );
}
