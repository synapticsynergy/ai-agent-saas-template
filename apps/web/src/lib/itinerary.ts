import type {
  Itinerary as GeneratedItinerary,
  PlanStopCreate as GeneratedStop,
} from "@saas/contracts";

/**
 * Itinerary types for the UI.
 *
 * The generated contracts mark every field with a server-side default as
 * optional, because the wire format may omit it. Rather than making every
 * component defend against `undefined`, `asItinerary` normalises once at the
 * boundary and hands the UI a fully-populated value.
 */

export interface ItineraryStop extends GeneratedStop {
  estimated_cost: number;
  reason: string;
}

export interface Itinerary extends GeneratedItinerary {
  title: string;
  estimated_cost: number;
  estimated_walk_distance_km: number;
  currency: string;
  saved: boolean;
  stops: ItineraryStop[];
}

export const EMPTY_ITINERARY: Itinerary = {
  plan_id: null,
  title: "",
  start_time: null,
  estimated_cost: 0,
  estimated_walk_distance_km: 0,
  currency: "USD",
  latitude: null,
  longitude: null,
  stops: [],
  saved: false,
};

function normalizeStop(stop: GeneratedStop): ItineraryStop {
  return {
    ...stop,
    estimated_cost: stop.estimated_cost ?? 0,
    reason: stop.reason ?? "",
  };
}

/** Narrow unknown agent state to a fully-populated itinerary, or null. */
export function asItinerary(value: unknown): Itinerary | null {
  if (!value || typeof value !== "object") return null;

  const candidate = value as Partial<GeneratedItinerary>;
  if (!Array.isArray(candidate.stops)) return null;

  return {
    ...EMPTY_ITINERARY,
    ...candidate,
    title: candidate.title ?? "",
    estimated_cost: candidate.estimated_cost ?? 0,
    estimated_walk_distance_km: candidate.estimated_walk_distance_km ?? 0,
    currency: candidate.currency ?? "USD",
    saved: candidate.saved ?? false,
    stops: candidate.stops.map(normalizeStop),
  };
}
