"use client";

import { useCallback, useMemo, useState } from "react";

export type StageStatus = "pending" | "running" | "done" | "error";

/** One line in the progress checklist the overlay renders. */
export interface ProgressStage {
  id: string;
  label: string;
  status: StageStatus;
  detail?: string;
}

/**
 * Translate AG-UI step and tool events into a progress checklist.
 *
 * The stage names come from `saas_contracts.streaming.ProgressStage`, so the
 * agent and the UI share one vocabulary instead of each inventing its own.
 */

const STAGE_LABELS: Record<string, string> = {
  locating: "Confirming location",
  searching_events: "Finding live events",
  searching_places: "Finding nearby venues",
  optimizing_route: "Checking the route",
  building_itinerary: "Building the itinerary",
  done: "Done",
};

const TOOL_LABELS: Record<string, string> = {
  search_places: "Searching venues",
  search_events: "Searching events",
  build_route: "Measuring the walk",
  get_place_details: "Loading venue details",
  save_plan: "Saving the plan",
};

export function useAgentProgress() {
  const [statuses, setStatuses] = useState<Record<string, StageStatus>>({});
  const [details, setDetails] = useState<Record<string, string>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const touch = useCallback((id: string) => {
    setOrder((current) => (current.includes(id) ? current : [...current, id]));
  }, []);

  const startRun = useCallback(() => {
    setStatuses({});
    setDetails({});
    setOrder([]);
    setError(null);
    setRunning(true);
  }, []);

  const finishRun = useCallback(() => {
    setRunning(false);
    setStatuses((current) => {
      const next = { ...current };
      for (const key of Object.keys(next)) {
        if (next[key] === "running") next[key] = "done";
      }
      return next;
    });
  }, []);

  const failRun = useCallback((message: string) => {
    setRunning(false);
    setError(message);
    setStatuses((current) => {
      const next = { ...current };
      for (const key of Object.keys(next)) {
        if (next[key] === "running") next[key] = "error";
      }
      return next;
    });
  }, []);

  const stepStarted = useCallback(
    (name: string) => {
      touch(name);
      setStatuses((current) => ({ ...current, [name]: "running" }));
    },
    [touch],
  );

  const stepFinished = useCallback(
    (name: string) => {
      touch(name);
      setStatuses((current) => ({ ...current, [name]: "done" }));
    },
    [touch],
  );

  const toolStarted = useCallback(
    (toolCallId: string, toolName: string) => {
      const id = `tool:${toolCallId}`;
      touch(id);
      setStatuses((current) => ({ ...current, [id]: "running" }));
      setDetails((current) => ({ ...current, [id]: TOOL_LABELS[toolName] ?? toolName }));
    },
    [touch],
  );

  const toolFinished = useCallback((toolCallId: string, detail?: string) => {
    const id = `tool:${toolCallId}`;
    setStatuses((current) => ({ ...current, [id]: "done" }));
    if (detail) setDetails((current) => ({ ...current, [id]: detail }));
  }, []);

  const stages = useMemo<ProgressStage[]>(
    () =>
      order.map((id) => ({
        id,
        label: id.startsWith("tool:")
          ? (details[id] ?? "Working")
          : (STAGE_LABELS[id] ?? id.replaceAll("_", " ")),
        status: statuses[id] ?? "pending",
        detail: id.startsWith("tool:") ? undefined : details[id],
      })),
    [order, statuses, details],
  );

  return {
    stages,
    running,
    error,
    startRun,
    finishRun,
    failRun,
    stepStarted,
    stepFinished,
    toolStarted,
    toolFinished,
  };
}
