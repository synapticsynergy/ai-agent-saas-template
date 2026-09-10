"use client";

import { CopilotPopup } from "@copilotkit/react-core/v2";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Snackbar from "@mui/material/Snackbar";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useCallback, useState } from "react";

import { ItineraryMap } from "@/components/ItineraryMap";
import { ItineraryOverlay } from "@/components/ItineraryOverlay";
import { usePlannerAgent, type PlannerLocation } from "@/hooks/usePlannerAgent";
import { formatMoney } from "@/lib/format";

import "@copilotkit/react-core/v2/styles.css";

/**
 * The planner.
 *
 * The map fills the viewport and the itinerary floats over it. The assistant
 * lives in CopilotKit's popup — a button in the corner that slides a panel in —
 * because the plan, not the conversation, is what the person is here to look at.
 *
 * Both surfaces drive the same agent: the popup sends the messages, and this
 * view subscribes to the resulting AG-UI events. Nothing is duplicated, and the
 * map updates while the person is still reading the reply.
 */

const GREETING =
  "Hi. Tell me the kind of evening you want and I'll plan it — dinner, live " +
  "music and drinks, walkable, under $100. Then ask me to make it cheaper, " +
  "change the music, or save it.";

export function PlannerView({
  location,
  canSave,
}: {
  location: PlannerLocation;
  canSave: boolean;
}) {
  const planner = usePlannerAgent(location);
  const [chatOpen, setChatOpen] = useState(false);
  const [selectedRaw, setSelected] = useState(0);
  const [dismissedSaveToastFor, setDismissedSaveToastFor] = useState<string | null>(null);

  // Both of these are derived during render rather than synchronised by an
  // effect. A replan can return fewer stops, and an effect that corrected the
  // selection afterwards would render one frame pointing at a stop that no
  // longer exists.
  const stopCount = planner.itinerary?.stops.length ?? 0;
  const selected = selectedRaw < stopCount ? selectedRaw : 0;

  // Keyed on the plan id so the confirmation reappears for the next plan the
  // person saves, but not again for one they have already dismissed.
  const savedPlanId = planner.itinerary?.saved ? (planner.itinerary.plan_id ?? "saved") : null;
  const showSaveToast = savedPlanId !== null && savedPlanId !== dismissedSaveToastFor;

  const requestSave = useCallback(() => {
    void planner.send("Save this plan.");
  }, [planner]);

  return (
    <Box sx={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <ItineraryMap
        stops={planner.itinerary?.stops ?? []}
        selectedIndex={selected}
        onSelect={setSelected}
        center={location}
      />

      <ItineraryOverlay
        itinerary={planner.itinerary}
        running={planner.running}
        stages={planner.stages}
        error={planner.error}
        canSave={canSave}
        selectedIndex={selected}
        onSelect={setSelected}
        onSave={requestSave}
        onOpenAssistant={() => setChatOpen(true)}
      />

      {!canSave ? (
        <Alert
          severity="info"
          sx={{
            position: "absolute",
            bottom: 16,
            left: { xs: 16, md: 20 },
            maxWidth: 400,
            zIndex: 1000,
          }}
        >
          Your role can view plans but not save them. Saving requires the <code>plans:write</code>{" "}
          permission.
        </Alert>
      ) : null}

      <CopilotPopup
        agentId="planner"
        open={chatOpen}
        onOpenChange={setChatOpen}
        clickOutsideToClose={false}
        labels={{ chatInputPlaceholder: "Describe your evening…" }}
      />

      <ApprovalDialog planner={planner} />

      <Snackbar
        open={showSaveToast}
        autoHideDuration={5000}
        onClose={() => setDismissedSaveToastFor(savedPlanId)}
        message="Plan saved to your organization."
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Box>
  );
}

function ApprovalDialog({ planner }: { planner: ReturnType<typeof usePlannerAgent> }) {
  const approval = planner.approval;
  const detail = (approval?.detail ?? {}) as {
    title?: string;
    estimated_cost?: number;
    stop_count?: number;
  };

  return (
    // MUI points aria-labelledby at the DialogTitle, so this dialog's
    // accessible name is "Save this plan?" — which is how tests tell it apart
    // from the chat popup, itself a role="dialog".
    <Dialog open={Boolean(approval)} onClose={planner.dismissApproval} maxWidth="xs" fullWidth>
      <DialogTitle>Save this plan?</DialogTitle>
      <DialogContent>
        <DialogContentText component="div">
          <Stack spacing={1}>
            <Typography variant="body2">
              {detail.title ?? "Your evening"} — {detail.stop_count ?? 0} stops, about{" "}
              {formatMoney(detail.estimated_cost ?? 0)}.
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Saving writes the plan to your organization. Your account still has to have permission
              to do it.
            </Typography>
          </Stack>
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={planner.dismissApproval}>Not now</Button>
        <Button variant="contained" onClick={() => void planner.approve()}>
          Save plan
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export { GREETING };
export default PlannerView;
