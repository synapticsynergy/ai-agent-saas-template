"use client";

import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import dynamic from "next/dynamic";

import type { PlannerLocation } from "@/hooks/usePlannerAgent";

/**
 * Client-only boundary for the planner.
 *
 * Leaflet reaches for `window` while its module is evaluating, so it cannot be
 * server-rendered. Isolating the dynamic import here keeps the page itself a
 * Server Component, which is what reads the session and decides permissions.
 */
const PlannerView = dynamic(() => import("@/components/PlannerView").then((m) => m.PlannerView), {
  ssr: false,
  loading: () => (
    <Box sx={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
      <CircularProgress />
    </Box>
  ),
});

export function PlannerSurface(props: { location: PlannerLocation; canSave: boolean }) {
  return <PlannerView {...props} />;
}

export default PlannerSurface;
