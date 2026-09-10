"use client";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useMemo } from "react";
import Map, { Layer, Marker, Source } from "react-map-gl/maplibre";

import { publicEnv } from "@/lib/env";

import "maplibre-gl/dist/maplibre-gl.css";

/** A CSS size, or one per MUI breakpoint. */
export type ResponsiveSize = number | string | Partial<Record<string, number | string>>;

export interface MapStop {
  name: string;
  latitude: number;
  longitude: number;
}

/**
 * Itinerary map.
 *
 * MapLibre with a configurable style URL, so the mapping provider stays
 * replaceable: point `NEXT_PUBLIC_MAP_STYLE_URL` at your own tiles and nothing
 * else changes.
 */
export function ItineraryMap({
  stops,
  selectedIndex = 0,
  onSelect,
  height = 380,
}: {
  stops: MapStop[];
  selectedIndex?: number;
  onSelect?: (index: number) => void;
  /** Responsive breakpoint values are accepted, e.g. `{ xs: 300, md: 460 }`. */
  height?: ResponsiveSize;
}) {
  const bounds = useMemo(() => {
    if (stops.length === 0) return null;

    const lats = stops.map((s) => s.latitude);
    const lons = stops.map((s) => s.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);

    // Pad so markers are not flush against the viewport edge.
    const padLat = Math.max((maxLat - minLat) * 0.35, 0.004);
    const padLon = Math.max((maxLon - minLon) * 0.35, 0.004);

    return {
      center: { latitude: (minLat + maxLat) / 2, longitude: (minLon + maxLon) / 2 },
      bbox: [minLon - padLon, minLat - padLat, maxLon + padLon, maxLat + padLat] as [
        number,
        number,
        number,
        number,
      ],
    };
  }, [stops]);

  const routeLine = useMemo(
    () => ({
      type: "Feature" as const,
      properties: {},
      geometry: {
        type: "LineString" as const,
        coordinates: stops.map((stop) => [stop.longitude, stop.latitude]),
      },
    }),
    [stops],
  );

  if (!bounds) {
    return (
      <Box
        sx={{
          height,
          display: "grid",
          placeItems: "center",
          borderRadius: 1,
          bgcolor: "action.hover",
        }}
      >
        <Typography variant="body2" color="text.secondary">
          The map appears once the itinerary has stops.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height, borderRadius: 1, overflow: "hidden" }}>
      <Map
        initialViewState={{ bounds: bounds.bbox, fitBoundsOptions: { padding: 48 } }}
        mapStyle={publicEnv.mapStyleUrl}
        style={{ width: "100%", height: "100%" }}
        attributionControl={{ compact: true }}
      >
        {stops.length > 1 ? (
          <Source id="route" type="geojson" data={routeLine}>
            <Layer
              id="route-line"
              type="line"
              paint={{
                "line-color": "#3d5afe",
                "line-width": 3,
                "line-dasharray": [2, 1.5],
                "line-opacity": 0.7,
              }}
            />
          </Source>
        ) : null}

        {stops.map((stop, index) => (
          <Marker
            key={`${stop.name}-${index}`}
            latitude={stop.latitude}
            longitude={stop.longitude}
            anchor="center"
            onClick={onSelect ? () => onSelect(index) : undefined}
          >
            <Box
              aria-label={`Stop ${index + 1}: ${stop.name}`}
              sx={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
                fontSize: 13,
                fontWeight: 700,
                color: "common.white",
                cursor: onSelect ? "pointer" : "default",
                bgcolor: index === selectedIndex ? "primary.main" : "text.disabled",
                boxShadow: 2,
                transition: "background-color 120ms",
              }}
            >
              {index + 1}
            </Box>
          </Marker>
        ))}
      </Map>
    </Box>
  );
}

export default ItineraryMap;
