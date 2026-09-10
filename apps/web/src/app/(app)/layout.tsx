/**
 * Authenticated area.
 *
 * Enforces the session by placement: every page below this layout has one, so
 * no page has to remember to check. The API enforces the same identity
 * independently on every request.
 *
 * The visual shell lives in the nested groups, because the planner wants the
 * whole viewport for its map while everything else wants a normal padded page.
 */

// Every page here depends on the current session, so none can be prerendered.
// Without this the fixture identity would be baked into a static build.
export const dynamic = "force-dynamic";

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return children;
}
