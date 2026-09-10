import { AppShell } from "@/components/AppShell";
import { isDevFixtureAuth, requireSession } from "@/lib/auth";

/** Normal pages: a padded, max-width container inside the app shell. */
export default async function StandardLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();

  return (
    <AppShell session={session} devFixtureAuth={isDevFixtureAuth}>
      {children}
    </AppShell>
  );
}
