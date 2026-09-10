import { describe, expect, it } from "vitest";

import { categoryLabel, formatDistance, formatDuration, formatMoney, formatTime } from "./format";

describe("formatMoney", () => {
  it("rounds to whole units", () => {
    expect(formatMoney(84.4)).toBe("$84");
  });

  it("handles zero", () => {
    expect(formatMoney(0)).toBe("$0");
  });
});

describe("formatDistance", () => {
  it("uses metres below a kilometre", () => {
    expect(formatDistance(0.52)).toBe("520 m");
  });

  it("uses kilometres above one", () => {
    expect(formatDistance(2.14)).toBe("2.1 km");
  });

  it("handles zero", () => {
    expect(formatDistance(0)).toBe("0 m");
  });
});

describe("formatDuration", () => {
  it("shows minutes under an hour", () => {
    expect(formatDuration(42)).toBe("42 min");
  });

  it("shows whole hours without stray minutes", () => {
    expect(formatDuration(120)).toBe("2 h");
  });

  it("shows hours and minutes", () => {
    expect(formatDuration(95)).toBe("1 h 35 min");
  });
});

describe("formatTime", () => {
  it("returns an empty string for missing input", () => {
    expect(formatTime(null)).toBe("");
    expect(formatTime(undefined)).toBe("");
  });

  it("returns an empty string for an unparseable value", () => {
    expect(formatTime("not a date")).toBe("");
  });

  it("formats a valid timestamp", () => {
    expect(formatTime("2030-06-01T19:00:00Z")).toMatch(/\d/);
  });
});

describe("categoryLabel", () => {
  it("maps known categories to display labels", () => {
    expect(categoryLabel("music")).toBe("Live music");
  });

  it("falls back to the raw value for unknown categories", () => {
    expect(categoryLabel("skydiving")).toBe("skydiving");
  });
});
