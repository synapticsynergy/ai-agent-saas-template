"use client";

import BookmarkAddedIcon from "@mui/icons-material/BookmarkAdded";
import DirectionsWalkIcon from "@mui/icons-material/DirectionsWalk";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import PaymentsIcon from "@mui/icons-material/Payments";
import PlaceIcon from "@mui/icons-material/Place";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import type { ProgressStage } from "@/hooks/useAgentProgress";
import { categoryLabel, formatDistance, formatMoney, formatTime } from "@/lib/format";
import type { Itinerary } from "@/lib/itinerary";

/**
 * The itinerary, floating over the map.
 *
 * This is the primary surface: the plan is application state rendered from the
 * agent's state snapshots, not text parsed out of a transcript. The chat is a
 * side panel for talking to the agent, not the place the plan lives.
 */

const PANEL_WIDTH = { xs: "calc(100vw - 32px)", sm: 400 } as const;

export function ItineraryOverlay({
  itinerary,
  running,
  stages,
  error,
  canSave,
  selectedIndex,
  onSelect,
  onSave,
  onOpenAssistant,
}: {
  itinerary: Itinerary | null;
  running: boolean;
  stages: ProgressStage[];
  error: string | null;
  canSave: boolean;
  selectedIndex: number;
  onSelect: (index: number) => void;
  onSave: () => void;
  onOpenAssistant: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const hasPlan = Boolean(itinerary && itinerary.stops.length > 0);

  return (
    <Stack
      spacing={1.5}
      sx={{
        position: "absolute",
        top: { xs: 12, md: 20 },
        left: { xs: 16, md: 20 },
        width: PANEL_WIDTH,
        maxHeight: { xs: "calc(100% - 24px)", md: "calc(100% - 40px)" },
        zIndex: 1000, // above Leaflet's panes and controls
        pointerEvents: "none",
        "& > *": { pointerEvents: "auto" },
      }}
    >
      <Header
        itinerary={itinerary}
        running={running}
        collapsed={collapsed}
        hasPlan={hasPlan}
        canSave={canSave}
        onToggle={() => setCollapsed((value) => !value)}
        onSave={onSave}
      />

      <Collapse in={!collapsed} sx={{ minHeight: 0, overflow: "hidden" }}>
        <Stack
          spacing={1.5}
          sx={{
            // The card stack scrolls on its own; the map behind it does not move.
            overflowY: "auto",
            overscrollBehavior: "contain",
            maxHeight: { xs: "55vh", md: "calc(100vh - 260px)" },
            pb: 1,
            pr: 0.5,
          }}
        >
          {error ? <Alert severity="error">{error}</Alert> : null}

          {running && !hasPlan ? <ProgressCard stages={stages} /> : null}

          {!running && !hasPlan && !error ? <EmptyState onOpenAssistant={onOpenAssistant} /> : null}

          {hasPlan
            ? itinerary!.stops.map((stop, index) => (
                <StopCard
                  key={`${stop.external_id ?? stop.name}-${index}`}
                  index={index}
                  stop={stop}
                  currency={itinerary!.currency}
                  selected={index === selectedIndex}
                  onSelect={() => onSelect(index)}
                />
              ))
            : null}

          {running && hasPlan ? <ProgressCard stages={stages} compact /> : null}
        </Stack>
      </Collapse>
    </Stack>
  );
}

function Header({
  itinerary,
  running,
  collapsed,
  hasPlan,
  canSave,
  onToggle,
  onSave,
}: {
  itinerary: Itinerary | null;
  running: boolean;
  collapsed: boolean;
  hasPlan: boolean;
  canSave: boolean;
  onToggle: () => void;
  onSave: () => void;
}) {
  const saved = itinerary?.saved ?? false;

  return (
    <Paper
      elevation={0}
      data-testid="itinerary-header"
      sx={{
        bgcolor: "#14171a",
        color: "common.white",
        borderColor: "transparent",
        borderRadius: 2.5,
        px: 2,
        py: 1.5,
        boxShadow: "0 8px 28px rgba(0,0,0,.28)",
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <IconButton
          size="small"
          onClick={onToggle}
          aria-label={collapsed ? "Show the itinerary" : "Hide the itinerary"}
          aria-expanded={!collapsed}
          sx={{
            color: "inherit",
            transform: collapsed ? "rotate(180deg)" : "none",
            transition: "transform .18s",
          }}
        >
          <ExpandLessIcon />
        </IconButton>

        <Typography variant="h4" noWrap sx={{ flexGrow: 1, minWidth: 0 }}>
          {itinerary?.title || "Tonight"}
        </Typography>

        {running ? <CircularProgress size={18} sx={{ color: "inherit" }} /> : null}

        <Tooltip
          title={
            saved
              ? "Already saved to your organization"
              : canSave
                ? "Save this plan"
                : "Your role cannot save plans"
          }
        >
          {/* A span keeps the tooltip working while the button is disabled. */}
          <span>
            <IconButton
              size="small"
              onClick={onSave}
              disabled={!hasPlan || saved || !canSave || running}
              aria-label="Save this plan"
              data-testid="save-plan"
              sx={{
                color: "#14171a",
                bgcolor: "common.white",
                "&:hover": { bgcolor: "grey.200" },
                "&.Mui-disabled": { bgcolor: "rgba(255,255,255,.25)", color: "rgba(0,0,0,.4)" },
              }}
            >
              {saved ? (
                <BookmarkAddedIcon fontSize="small" />
              ) : (
                <SaveOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </span>
        </Tooltip>
      </Stack>

      {hasPlan ? (
        <Stack
          direction="row"
          spacing={0.75}
          useFlexGap
          sx={{ flexWrap: "wrap", mt: 1.25, pl: 0.5 }}
        >
          <SummaryChip
            icon={<PaymentsIcon />}
            testId="itinerary-cost"
            label={formatMoney(itinerary!.estimated_cost, itinerary!.currency)}
          />
          <SummaryChip
            icon={<DirectionsWalkIcon />}
            label={formatDistance(itinerary!.estimated_walk_distance_km)}
          />
          <SummaryChip
            icon={<PlaceIcon />}
            testId="itinerary-stop-count"
            label={`${itinerary!.stops.length} stops`}
          />
          {itinerary!.saved ? (
            <SummaryChip testId="itinerary-saved" label="Saved" tone="success" />
          ) : null}
        </Stack>
      ) : null}
    </Paper>
  );
}

function SummaryChip({
  icon,
  label,
  testId,
  tone,
}: {
  icon?: React.ReactElement;
  label: string;
  testId?: string;
  tone?: "success";
}) {
  return (
    <Chip
      icon={icon}
      label={label}
      data-testid={testId}
      sx={{
        color: "common.white",
        bgcolor: tone === "success" ? "success.dark" : "rgba(255,255,255,.14)",
        "& .MuiChip-icon": { color: "inherit", fontSize: 16 },
      }}
    />
  );
}

function StopCard({
  index,
  stop,
  currency,
  selected,
  onSelect,
}: {
  index: number;
  stop: Itinerary["stops"][number];
  currency: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <Card
      data-testid="itinerary-stop"
      data-selected={selected}
      sx={{
        borderRadius: 2.5,
        borderColor: selected ? "primary.main" : "divider",
        boxShadow: selected ? "0 6px 22px rgba(0,0,0,.16)" : "0 2px 10px rgba(0,0,0,.10)",
        transition: "box-shadow .15s, border-color .15s",
      }}
    >
      <CardActionArea onClick={onSelect} sx={{ p: 1.75, alignItems: "stretch" }}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start" }}>
          <Box
            aria-hidden
            sx={{
              minWidth: 26,
              height: 26,
              mt: 0.25,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              fontSize: 13,
              fontWeight: 700,
              color: "common.white",
              bgcolor: selected ? "primary.main" : "#14171a",
            }}
          >
            {index + 1}
          </Box>

          <Stack spacing={0.5} sx={{ flexGrow: 1, minWidth: 0 }}>
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              sx={{ alignItems: "center", flexWrap: "wrap" }}
            >
              <Typography variant="subtitle2" sx={{ minWidth: 0 }}>
                {stop.name}
              </Typography>
              <Chip variant="outlined" label={categoryLabel(stop.category)} />
            </Stack>

            <Typography variant="body2" color="text.secondary">
              {formatTime(stop.start_time)} – {formatTime(stop.end_time)}
              {stop.estimated_cost > 0
                ? ` · ${formatMoney(stop.estimated_cost, currency)} pp`
                : " · free"}
            </Typography>

            {stop.reason ? (
              <Typography variant="body2" color="text.secondary">
                {stop.reason}
              </Typography>
            ) : null}

            {stop.address ? (
              <Typography variant="caption" color="text.disabled">
                {stop.address}
              </Typography>
            ) : null}
          </Stack>
        </Stack>
      </CardActionArea>
    </Card>
  );
}

function ProgressCard({ stages, compact = false }: { stages: ProgressStage[]; compact?: boolean }) {
  const visible = compact ? stages.slice(-3) : stages;

  return (
    <Paper sx={{ borderRadius: 2.5, p: 1.75 }} aria-live="polite" data-testid="agent-progress">
      {visible.length === 0 ? (
        <Stack spacing={1}>
          <Skeleton variant="text" width="55%" />
          <Skeleton variant="rounded" height={54} />
        </Stack>
      ) : (
        <Stack spacing={0.75}>
          {visible.map((stage) => (
            <Stack key={stage.id} direction="row" spacing={1.25} sx={{ alignItems: "center" }}>
              <StageDot status={stage.status} />
              <Typography
                variant="body2"
                color={stage.status === "pending" ? "text.disabled" : "text.primary"}
                sx={{ flexGrow: 1, minWidth: 0 }}
                noWrap
              >
                {stage.label}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Paper>
  );
}

function StageDot({ status }: { status: ProgressStage["status"] }) {
  if (status === "running") return <CircularProgress size={13} thickness={6} />;

  const color =
    status === "done" ? "success.main" : status === "error" ? "error.main" : "text.disabled";

  return (
    <Box sx={{ width: 13, display: "grid", placeItems: "center" }}>
      <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: color }} />
    </Box>
  );
}

function EmptyState({ onOpenAssistant }: { onOpenAssistant: () => void }) {
  return (
    <Paper sx={{ borderRadius: 2.5, p: 2.25 }}>
      <Stack spacing={1.25}>
        <Typography variant="subtitle2">No itinerary yet</Typography>
        <Typography variant="body2" color="text.secondary">
          Open the assistant and describe the evening you want — dinner, live music and drinks,
          walkable, under $100.
        </Typography>
        <Chip
          label="Open the assistant"
          color="primary"
          onClick={onOpenAssistant}
          data-testid="open-assistant"
          sx={{ alignSelf: "flex-start" }}
        />
      </Stack>
    </Paper>
  );
}

export default ItineraryOverlay;
