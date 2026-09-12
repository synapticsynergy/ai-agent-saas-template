"""MCP App: interactive itinerary map.

Registered as a ``ui://`` HTML resource and bound to the ``render_itinerary``
tool, per the MCP Apps extension. An MCP host that supports the extension
renders this document and passes it the tool's structured output.

Hosts that do not support MCP Apps simply receive the structured itinerary as
normal tool output and render it themselves — which is what apps/web does today.
See docs/adr/ADR-007 for why both paths exist.

The document is deliberately dependency-free: MCP App resources are inlined
into the host's sandboxed frame, where a CDN fetch may be blocked by CSP.
"""

from __future__ import annotations

ITINERARY_MAP_URI = "ui://itinerary/map"

ITINERARY_MAP_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Itinerary</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff;
    --surface: #f6f7f9;
    --border: #e0e3e7;
    --text: #1a1d21;
    --muted: #5f6672;
    --accent: #3d5afe;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14171a; --surface: #1c2024; --border: #2c3138;
      --text: #e8eaed; --muted: #9aa1ab;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 16px; background: var(--bg); color: var(--text);
    font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .summary { color: var(--muted); margin-bottom: 16px; }
  .layout { display: grid; gap: 16px; grid-template-columns: 1fr; }
  @media (min-width: 720px) { .layout { grid-template-columns: 260px 1fr; } }
  svg { width: 100%; height: auto; background: var(--surface);
        border: 1px solid var(--border); border-radius: 8px; }
  ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  li { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px;
       background: var(--surface); cursor: pointer; }
  li[aria-selected="true"] { border-color: var(--accent); }
  .name { font-weight: 600; }
  .meta { color: var(--muted); font-size: 13px; }
  .empty { color: var(--muted); padding: 24px; text-align: center; }
</style>
</head>
<body>
<div id="root"><p class="empty">Waiting for itinerary data…</p></div>
<script>
(function () {
  var root = document.getElementById("root");
  var selected = 0;

  function money(value) {
    return "$" + Number(value || 0).toFixed(0);
  }

  function clockTime(iso) {
    if (!iso) return "";
    var date = new Date(iso);
    if (isNaN(date)) return "";
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  // Equirectangular projection is accurate enough at city scale and avoids
  // pulling in a mapping library that the host sandbox may block.
  function project(stops, width, height, pad) {
    var lats = stops.map(function (s) { return s.latitude; });
    var lons = stops.map(function (s) { return s.longitude; });
    var minLat = Math.min.apply(null, lats), maxLat = Math.max.apply(null, lats);
    var minLon = Math.min.apply(null, lons), maxLon = Math.max.apply(null, lons);
    var spanLat = Math.max(maxLat - minLat, 0.0015);
    var spanLon = Math.max(maxLon - minLon, 0.0015);

    return stops.map(function (stop) {
      return {
        x: pad + ((stop.longitude - minLon) / spanLon) * (width - 2 * pad),
        y: height - pad - ((stop.latitude - minLat) / spanLat) * (height - 2 * pad)
      };
    });
  }

  function render(itinerary) {
    var stops = (itinerary && itinerary.stops) || [];
    if (!stops.length) {
      root.innerHTML = '<p class="empty">No stops in this itinerary yet.</p>';
      return;
    }

    var width = 480, height = 320, pad = 28;
    var points = project(stops, width, height, pad);

    var path = points.map(function (p, i) {
      return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1);
    }).join(" ");

    var markers = points.map(function (p, i) {
      var fill = i === selected ? "var(--accent)" : "var(--muted)";
      return '<g><circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) +
        '" r="11" fill="' + fill + '"></circle>' +
        '<text x="' + p.x.toFixed(1) + '" y="' + (p.y + 4).toFixed(1) +
        '" text-anchor="middle" fill="#fff" font-size="12">' + (i + 1) + "</text></g>";
    }).join("");

    var list = stops.map(function (stop, i) {
      return '<li data-index="' + i + '" aria-selected="' + (i === selected) + '">' +
        '<div class="name">' + (i + 1) + ". " + escapeHtml(stop.name) + "</div>" +
        '<div class="meta">' + escapeHtml(stop.category) + " · " +
        clockTime(stop.start_time) + " · " + money(stop.estimated_cost) + "</div>" +
        (stop.reason ? '<div class="meta">' + escapeHtml(stop.reason) + "</div>" : "") +
        "</li>";
    }).join("");

    root.innerHTML =
      "<h1>" + escapeHtml(itinerary.title || "Your evening") + "</h1>" +
      '<div class="summary">' + money(itinerary.estimated_cost) + " · " +
      Number(itinerary.estimated_walk_distance_km || 0).toFixed(1) + " km walking · " +
      stops.length + " stops</div>" +
      '<div class="layout"><ol>' + list + "</ol>" +
      '<svg viewBox="0 0 ' + width + " " + height + '" role="img" ' +
      'aria-label="Map of itinerary stops">' +
      '<path d="' + path + '" fill="none" stroke="var(--border)" ' +
      'stroke-width="3" stroke-dasharray="6 4"></path>' + markers + "</svg></div>";

    root.querySelectorAll("li").forEach(function (item) {
      item.addEventListener("click", function () {
        selected = Number(item.getAttribute("data-index"));
        render(itinerary);
      });
    });
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // The MCP Apps host delivers tool output via postMessage into the frame.
  window.addEventListener("message", function (event) {
    var data = event.data || {};
    var payload = data.structuredContent || data.toolOutput || data.result || data;
    if (payload && payload.itinerary) render(payload.itinerary);
    else if (payload && payload.stops) render(payload);
  });

  if (window.parent !== window) {
    window.parent.postMessage({ type: "mcp-app-ready" }, "*");
  }
})();
</script>
</body>
</html>
"""
