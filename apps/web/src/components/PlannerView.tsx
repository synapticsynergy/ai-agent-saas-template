"use client";

import SendIcon from "@mui/icons-material/Send";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { AgentProgress } from "@/components/AgentProgress";
import { ItineraryMap } from "@/components/ItineraryMap";
import { ItineraryPanel } from "@/components/ItineraryPanel";
import { usePlannerAgent, type PlannerLocation } from "@/hooks/usePlannerAgent";
import { formatMoney } from "@/lib/format";

const EXAMPLE_REQUEST =
  "Plan my evening near me. I want dinner, live music, and drinks. Keep it walkable and under $100.";

const FOLLOW_UPS = [
  "Make it cheaper.",
  "Replace the live music with jazz.",
  "Keep it closer together.",
  "Save this plan.",
];

/**
 * The planner.
 *
 * The itinerary — not a chat transcript — is the primary surface. The
 * assistant's message is supporting context beside it, and the plan itself is
 * rendered from agent state.
 */
export function PlannerView({
  location,
  canSave,
}: {
  location: PlannerLocation;
  canSave: boolean;
}) {
  const planner = usePlannerAgent(location);
  const [input, setInput] = useState("");
  const [selected, setSelected] = useState(0);

  const submit = async (message: string) => {
    if (!message.trim() || planner.running) return;
    setInput("");
    setSelected(0);
    await planner.send(message);
  };

  return (
    <Stack spacing={{ xs: 2, md: 3 }}>
      <Stack spacing={1}>
        <Typography variant="h2">Tonight</Typography>
        <Typography variant="body2" color="text.secondary">
          Describe the evening you want, then refine it in plain language.
        </Typography>
      </Stack>

      <Paper sx={{ p: { xs: 1.5, md: 2 } }}>
        <Stack spacing={1.5}>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submit(input);
              }
            }}
            placeholder={EXAMPLE_REQUEST}
            disabled={planner.running}
            label="What kind of evening?"
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label="Send request"
                      onClick={() => void submit(input)}
                      disabled={planner.running || !input.trim()}
                      edge="end"
                    >
                      <SendIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />

          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
            {!planner.itinerary ? (
              <Chip
                label="Try the example"
                onClick={() => void submit(EXAMPLE_REQUEST)}
                disabled={planner.running}
              />
            ) : (
              FOLLOW_UPS.map((suggestion) => (
                <Chip
                  key={suggestion}
                  label={suggestion}
                  onClick={() => void submit(suggestion)}
                  disabled={planner.running}
                />
              ))
            )}
          </Stack>
        </Stack>
      </Paper>

      <AgentProgress stages={planner.stages} visible={planner.running} />

      {planner.error ? <Alert severity="error">{planner.error}</Alert> : null}

      {!canSave ? (
        <Alert severity="info">
          Your role can view plans but not save them. The assistant will still plan an evening;
          saving requires the <code>plans:write</code> permission.
        </Alert>
      ) : null}

      {planner.assistantMessage ? (
        <Alert severity="success" icon={false}>
          {planner.assistantMessage}
        </Alert>
      ) : null}

      <Box
        sx={{
          display: "grid",
          gap: { xs: 2, md: 3 },
          gridTemplateColumns: { xs: "1fr", md: "minmax(0, 5fr) minmax(0, 7fr)" },
          alignItems: "start",
        }}
      >
        <ItineraryPanel
          itinerary={planner.itinerary}
          loading={planner.running}
          selectedIndex={selected}
          onSelect={setSelected}
        />

        <Paper sx={{ p: { xs: 1, md: 1.5 }, position: { md: "sticky" }, top: { md: 88 } }}>
          <ItineraryMap
            stops={planner.itinerary?.stops ?? []}
            selectedIndex={selected}
            onSelect={setSelected}
            height={{ xs: 300, md: 460 }}
          />
        </Paper>
      </Box>

      <ApprovalDialog planner={planner} />
    </Stack>
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

export default PlannerView;
