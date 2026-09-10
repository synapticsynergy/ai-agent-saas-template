"use client";

import DirectionsWalkIcon from "@mui/icons-material/DirectionsWalk";
import PaymentsIcon from "@mui/icons-material/Payments";
import PlaceIcon from "@mui/icons-material/Place";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardActionArea from "@mui/material/CardActionArea";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import type { Itinerary } from "@/lib/itinerary";
import { categoryLabel, formatDistance, formatMoney, formatTime } from "@/lib/format";

/**
 * The itinerary rendered as application state.
 *
 * The agent publishes the itinerary as an AG-UI state snapshot, and this
 * component renders that structure directly. It never parses the assistant's
 * prose — treating the plan as state rather than as text is what makes it
 * selectable, mappable and savable.
 */
export function ItineraryPanel({
  itinerary,
  loading = false,
  selectedIndex = 0,
  onSelect,
}: {
  itinerary: Itinerary | null;
  loading?: boolean;
  selectedIndex?: number;
  onSelect?: (index: number) => void;
}) {
  if (loading && !itinerary) {
    return (
      <Stack spacing={1.5} aria-busy="true" aria-label="Building your itinerary">
        <Skeleton variant="text" width="60%" height={32} />
        <Skeleton variant="rounded" height={92} />
        <Skeleton variant="rounded" height={92} />
        <Skeleton variant="rounded" height={92} />
      </Stack>
    );
  }

  if (!itinerary || itinerary.stops.length === 0) {
    return (
      <Alert severity="info">
        No itinerary yet. Describe the evening you want and the agent will build one.
      </Alert>
    );
  }

  return (
    <Stack spacing={2}>
      <Stack spacing={1}>
        <Stack
          direction="row"
          spacing={1}
          useFlexGap
          sx={{ alignItems: "center", flexWrap: "wrap" }}
        >
          <Typography variant="h3">{itinerary.title || "Your evening"}</Typography>
            {itinerary.saved ? (
            <Chip color="success" data-testid="itinerary-saved" label="Saved" />
          ) : null}
        </Stack>

        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            icon={<PaymentsIcon />}
            data-testid="itinerary-cost"
            label={formatMoney(itinerary.estimated_cost, itinerary.currency)}
          />
          <Chip
            icon={<DirectionsWalkIcon />}
            label={formatDistance(itinerary.estimated_walk_distance_km)}
          />
          <Chip
            icon={<PlaceIcon />}
            data-testid="itinerary-stop-count"
            label={`${itinerary.stops.length} stops`}
          />
        </Stack>
      </Stack>

      <Divider />

      <Stack spacing={1.5} component="ol" sx={{ listStyle: "none", m: 0, p: 0 }}>
        {itinerary.stops.map((stop, index) => (
          <Card
            key={`${stop.external_id ?? stop.name}-${index}`}
            component="li"
            data-testid="itinerary-stop"
            data-selected={index === selectedIndex}
            sx={{
              borderColor: index === selectedIndex ? "primary.main" : undefined,
            }}
          >
            <CardActionArea
              onClick={onSelect ? () => onSelect(index) : undefined}
              disabled={!onSelect}
              sx={{ p: { xs: 1.5, md: 2 }, alignItems: "stretch" }}
            >
              <Stack direction="row" spacing={2} sx={{ alignItems: "flex-start" }}>
                <Box
                  aria-hidden
                  sx={{
                    minWidth: 28,
                    height: 28,
                    borderRadius: "50%",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "common.white",
                    bgcolor: index === selectedIndex ? "primary.main" : "text.disabled",
                  }}
                >
                  {index + 1}
                </Box>

                <Stack spacing={0.5} sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Stack
                    direction="row"
                    spacing={1}
                    useFlexGap
                    sx={{ alignItems: "baseline", flexWrap: "wrap" }}
                  >
                    <Typography variant="subtitle2" noWrap sx={{ maxWidth: "100%" }}>
                      {stop.name}
                    </Typography>
                    <Chip variant="outlined" label={categoryLabel(stop.category)} />
                  </Stack>

                  <Typography variant="body2" color="text.secondary">
                    {formatTime(stop.start_time)} – {formatTime(stop.end_time)}
                    {stop.estimated_cost > 0
                      ? ` · ${formatMoney(stop.estimated_cost, itinerary.currency)} pp`
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
        ))}
      </Stack>
    </Stack>
  );
}

export default ItineraryPanel;
