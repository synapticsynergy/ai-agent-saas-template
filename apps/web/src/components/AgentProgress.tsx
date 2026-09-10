"use client";

import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutlineOutlined";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export type StageStatus = "pending" | "running" | "done" | "error";

export interface ProgressStage {
  id: string;
  label: string;
  status: StageStatus;
  detail?: string;
}

/**
 * Live agent progress.
 *
 * Driven by AG-UI step and tool events. Showing what the agent is *doing* — not
 * just a spinner — is the difference between a wait that feels broken and one
 * that feels like work happening.
 */
export function AgentProgress({ stages, visible }: { stages: ProgressStage[]; visible: boolean }) {
  return (
    <Collapse in={visible && stages.length > 0} unmountOnExit>
      <Paper sx={{ p: { xs: 1.5, md: 2 } }} aria-live="polite">
        <Stack spacing={1}>
          {stages.map((stage) => (
            <Stack key={stage.id} direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <StageIcon status={stage.status} />
              <Typography
                variant="body2"
                color={stage.status === "pending" ? "text.disabled" : "text.primary"}
                sx={{ flexGrow: 1 }}
              >
                {stage.label}
              </Typography>
              {stage.detail ? (
                <Typography variant="caption" color="text.secondary">
                  {stage.detail}
                </Typography>
              ) : null}
            </Stack>
          ))}
        </Stack>
      </Paper>
    </Collapse>
  );
}

function StageIcon({ status }: { status: StageStatus }) {
  const size = 18;

  if (status === "running") {
    return (
      <Box sx={{ width: size, height: size, display: "grid", placeItems: "center" }}>
        <CircularProgress size={14} thickness={6} />
      </Box>
    );
  }
  if (status === "done") {
    return <CheckCircleIcon color="success" sx={{ fontSize: size }} />;
  }
  if (status === "error") {
    return <ErrorOutlineIcon color="error" sx={{ fontSize: size }} />;
  }
  return <RadioButtonUncheckedIcon sx={{ fontSize: size, color: "text.disabled" }} />;
}

export default AgentProgress;
