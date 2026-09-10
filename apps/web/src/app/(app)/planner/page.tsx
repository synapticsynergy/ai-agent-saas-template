import type { Metadata } from "next";

import { CopilotProvider } from "@/components/CopilotProvider";
import { PlannerView } from "@/components/PlannerView";
import { hasPermission, requireSession } from "@/lib/auth";

export const metadata: Metadata = { title: "Planner" };

const DEFAULT_LOCATION = {
  latitude: Number(process.env.DEFAULT_LATITUDE ?? 45.5231),
  longitude: Number(process.env.DEFAULT_LONGITUDE ?? -122.6765),
};

export default async function PlannerPage() {
  const session = await requireSession();

  return (
    <CopilotProvider>
      <PlannerView location={DEFAULT_LOCATION} canSave={hasPermission(session, "plans:write")} />
    </CopilotProvider>
  );
}
