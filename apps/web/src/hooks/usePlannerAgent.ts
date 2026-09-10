"use client";

import type { AgentSubscriber } from "@ag-ui/client";
import { useAgent } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAgentProgress } from "@/hooks/useAgentProgress";
import { asItinerary, type Itinerary } from "@/lib/itinerary";

/**
 * Drives one planner conversation.
 *
 * Subscribes to the agent's AG-UI events and projects them into the three
 * things the UI actually renders: a progress checklist, the itinerary as
 * application state, and the assistant's message.
 *
 * The itinerary comes from `STATE_SNAPSHOT` events, never from parsing the
 * assistant's prose. That is what lets the plan be selectable, mappable and
 * savable rather than just readable.
 */

export interface ApprovalRequest {
  action: string;
  detail: Record<string, unknown>;
  runId?: string;
}

export interface PlannerLocation {
  latitude: number;
  longitude: number;
}

export function usePlannerAgent(location: PlannerLocation) {
  const { agent, isReady } = useAgent({ agentId: "planner" });
  const progress = useAgentProgress();

  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [assistantMessage, setAssistantMessage] = useState("");
  const [approval, setApproval] = useState<ApprovalRequest | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  // The subscriber closes over this ref so its callbacks always see the current
  // progress helpers, without re-subscribing to the agent on every render.
  const progressRef = useRef(progress);
  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  useEffect(() => {
    if (!isReady) return;

    const subscriber: AgentSubscriber = {
      onRunStartedEvent: () => {
        progressRef.current.startRun();
        setAssistantMessage("");
        setApproval(null);
      },
      onRunFinishedEvent: () => {
        progressRef.current.finishRun();
      },
      onRunErrorEvent: ({ event }) => {
        progressRef.current.failRun(event.message ?? "The agent run failed.");
      },
      onRunFailed: ({ error }) => {
        progressRef.current.failRun(error.message);
      },
      onStepStartedEvent: ({ event }) => {
        progressRef.current.stepStarted(event.stepName);
      },
      onStepFinishedEvent: ({ event }) => {
        progressRef.current.stepFinished(event.stepName);
      },
      onToolCallStartEvent: ({ event }) => {
        progressRef.current.toolStarted(event.toolCallId, event.toolCallName);
      },
      onToolCallEndEvent: ({ event }) => {
        progressRef.current.toolFinished(event.toolCallId);
      },
      onTextMessageContentEvent: ({ textMessageBuffer }) => {
        setAssistantMessage(textMessageBuffer);
      },
      onStateSnapshotEvent: ({ event }) => {
        const snapshot = event.snapshot as { itinerary?: unknown } | undefined;
        const next = asItinerary(snapshot?.itinerary);
        if (next) setItinerary(next);
      },
      onCustomEvent: ({ event }) => {
        if (event.name === "approval_requested") {
          const value = event.value as ApprovalRequest;
          setApproval(value);
        }
      },
    };

    const subscription = agent.subscribe(subscriber);
    return () => subscription.unsubscribe();
  }, [agent, isReady]);

  const send = useCallback(
    async (message: string, forwardedProps: Record<string, unknown> = {}) => {
      const text = message.trim();
      if (!text || !isReady || agent.isRunning) return;

      setHistory((current) => [...current, text]);

      agent.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: text,
      });

      // Merge into the agent's existing state rather than replacing it. The
      // agent publishes its resolved planning constraints there, and a
      // follow-up like "make it cheaper" needs them to survive the round trip —
      // overwriting the state loses the original budget and the revision
      // silently replans from scratch.
      //
      // Identity is deliberately absent: it is attached server-side in the
      // CopilotKit runtime route, never from the browser.
      agent.setState({
        ...(agent.state as Record<string, unknown>),
        ...location,
        itinerary: itinerary ?? undefined,
      });

      await agent.runAgent({ forwardedProps });
    },
    [agent, isReady, itinerary, location],
  );

  const approve = useCallback(async () => {
    const pending = approval;
    setApproval(null);
    if (!pending) return;

    // Re-sends the same intent with approval attached. The approval expresses
    // the user's intent only — the API still checks the permission.
    await send("Save this plan.", { approved: true });
  }, [approval, send]);

  const dismissApproval = useCallback(() => setApproval(null), []);

  return {
    isReady,
    running: agent.isRunning || progress.running,
    stages: progress.stages,
    error: progress.error,
    itinerary,
    assistantMessage,
    approval,
    history,
    send,
    approve,
    dismissApproval,
  };
}
