import { describe, expect, it } from "vitest";

import { asItinerary, EMPTY_ITINERARY } from "./itinerary";

/**
 * `asItinerary` is the boundary between untrusted agent state and the UI. It
 * has to be total: anything the agent sends either becomes a fully-populated
 * itinerary or becomes null, never a half-built object the components then
 * have to defend against.
 */
describe("asItinerary", () => {
  it("rejects non-objects", () => {
    expect(asItinerary(null)).toBeNull();
    expect(asItinerary(undefined)).toBeNull();
    expect(asItinerary("itinerary")).toBeNull();
    expect(asItinerary(42)).toBeNull();
  });

  it("rejects an object with no stops array", () => {
    expect(asItinerary({ title: "Evening" })).toBeNull();
    expect(asItinerary({ stops: "three" })).toBeNull();
  });

  it("accepts an empty itinerary", () => {
    const result = asItinerary({ stops: [] });
    expect(result).not.toBeNull();
    expect(result?.stops).toEqual([]);
  });

  it("fills in every field the agent omitted", () => {
    const result = asItinerary({ stops: [] });
    expect(result?.currency).toBe("USD");
    expect(result?.estimated_cost).toBe(0);
    expect(result?.estimated_walk_distance_km).toBe(0);
    expect(result?.saved).toBe(false);
    expect(result?.title).toBe("");
  });

  it("preserves the values the agent did send", () => {
    const result = asItinerary({
      title: "Dinner and live music",
      estimated_cost: 84,
      estimated_walk_distance_km: 2.1,
      saved: true,
      plan_id: "plan_1",
      stops: [],
    });

    expect(result?.title).toBe("Dinner and live music");
    expect(result?.estimated_cost).toBe(84);
    expect(result?.saved).toBe(true);
    expect(result?.plan_id).toBe("plan_1");
  });

  it("normalises stops so components need no fallbacks", () => {
    const result = asItinerary({
      stops: [
        {
          name: "Saltbox Diner",
          category: "dinner",
          start_time: "2030-06-01T19:00:00Z",
          end_time: "2030-06-01T20:30:00Z",
          latitude: 45.52,
          longitude: -122.68,
        },
      ],
    });

    expect(result?.stops[0]?.estimated_cost).toBe(0);
    expect(result?.stops[0]?.reason).toBe("");
  });

  it("does not mutate the empty template", () => {
    asItinerary({ stops: [], title: "Mutated" });
    expect(EMPTY_ITINERARY.title).toBe("");
  });
});
