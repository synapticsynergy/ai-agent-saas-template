"use client";

import Box from "@mui/material/Box";
import { useTheme } from "@mui/material/styles";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";

import { publicEnv } from "@/lib/env";

import "leaflet/dist/leaflet.css";

export interface MapStop {
  name: string;
  latitude: number;
  longitude: number;
}

/**
 * The itinerary map.
 *
 * Leaflet with raster tiles: no API key, no WebGL, and a legible street map at
 * city scale, which is what an itinerary needs. The tile URL and attribution
 * are configuration, so switching to a commercial provider is an environment
 * change rather than a rewrite.
 *
 * Markers are `divIcon`s rather than image pins so they can carry the stop
 * number and pick up the MUI palette — the map is part of the design system,
 * not a foreign object dropped into it.
 */

const MIN_SPAN_DEGREES = 0.004;

// Close-together stops would otherwise fit to maximum zoom, which loses the
// surrounding streets the walk actually happens on.
const MAX_FIT_ZOOM = 16;

function numberedIcon(index: number, selected: boolean, color: string): L.DivIcon {
  const size = selected ? 34 : 28;

  return L.divIcon({
    className: "itinerary-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `
      <div style="
        width:${size}px;height:${size}px;border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        background:${selected ? color : "#1a1d21"};
        color:#fff;font:600 ${selected ? 15 : 13}px/1 system-ui,sans-serif;
        border:2px solid #fff;
        box-shadow:0 2px 8px rgba(0,0,0,.35);
        transition:width .12s,height .12s;
      ">${index + 1}</div>`,
  });
}

/** Keeps the viewport framed on the itinerary as stops change. */
function FitBounds({ stops }: { stops: MapStop[] }) {
  const map = useMap();

  useEffect(() => {
    if (stops.length === 0) return;

    if (stops.length === 1) {
      const only = stops[0]!;
      map.setView([only.latitude, only.longitude], 15, { animate: true });
      return;
    }

    const bounds = L.latLngBounds(stops.map((s) => [s.latitude, s.longitude] as [number, number]));

    // Pad tiny bounds so a cluster of nearby stops does not zoom to maximum.
    if (
      bounds.getNorth() - bounds.getSouth() < MIN_SPAN_DEGREES &&
      bounds.getEast() - bounds.getWest() < MIN_SPAN_DEGREES
    ) {
      map.setView(bounds.getCenter(), MAX_FIT_ZOOM, { animate: true });
      return;
    }

    map.fitBounds(bounds, {
      maxZoom: MAX_FIT_ZOOM,
      // Generous left padding: the itinerary panel floats over the map there.
      paddingTopLeft: [window.innerWidth >= 900 ? 460 : 40, 120],
      paddingBottomRight: [80, 80],
      animate: true,
    });
  }, [map, stops]);

  return null;
}

/** Centres the selected stop when the list selection changes. */
function FollowSelection({ stops, selectedIndex }: { stops: MapStop[]; selectedIndex: number }) {
  const map = useMap();
  const selected = stops[selectedIndex];

  useEffect(() => {
    if (!selected) return;
    map.panTo([selected.latitude, selected.longitude], { animate: true, duration: 0.4 });
  }, [map, selected]);

  return null;
}

export function ItineraryMap({
  stops,
  selectedIndex = 0,
  onSelect,
  center,
}: {
  stops: MapStop[];
  selectedIndex?: number;
  onSelect?: (index: number) => void;
  /** Where to look before there is an itinerary. */
  center: { latitude: number; longitude: number };
}) {
  const theme = useTheme();
  const accent = theme.palette.primary.main;

  const route = useMemo(
    () => stops.map((stop) => [stop.latitude, stop.longitude] as [number, number]),
    [stops],
  );

  return (
    <Box
      sx={{
        position: "absolute",
        inset: 0,
        // Leaflet's own panes sit below the floating panels.
        "& .leaflet-container": { width: "100%", height: "100%", background: "#e8eaed" },
        "& .leaflet-control-attribution": { fontSize: 11 },
      }}
    >
      <MapContainer
        center={[center.latitude, center.longitude]}
        zoom={14}
        zoomControl={false}
        scrollWheelZoom
      >
        <TileLayer url={publicEnv.mapTileUrl} attribution={publicEnv.mapAttribution} maxZoom={19} />

        {route.length > 1 ? (
          <Polyline
            positions={route}
            pathOptions={{ color: accent, weight: 3, opacity: 0.75, dashArray: "6 8" }}
          />
        ) : null}

        {stops.map((stop, index) => (
          <Marker
            key={`${stop.name}-${index}`}
            position={[stop.latitude, stop.longitude]}
            icon={numberedIcon(index, index === selectedIndex, accent)}
            alt={`Stop ${index + 1}: ${stop.name}`}
            eventHandlers={onSelect ? { click: () => onSelect(index) } : undefined}
          />
        ))}

        <FitBounds stops={stops} />
        <FollowSelection stops={stops} selectedIndex={selectedIndex} />
      </MapContainer>
    </Box>
  );
}

export default ItineraryMap;
