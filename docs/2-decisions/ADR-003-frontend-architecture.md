# ADR-003: Frontend Architecture & Layout

## Status

Accepted

## Context

The original UI was Tkinter with `tkintermapview`. The refactored system needs a web-based UI. Two approaches were possible: (a) Gradio for rapid prototyping with auto-generated UI, or (b) hand-crafted HTML/JS with FastAPI backend. The earlier ADR-001 chose FastAPI. This ADR specifies the exact frontend architecture, rejecting Folium in favor of pure client-side Leaflet.js.

## Decision

### 1. No Folium — Client-Side Leaflet.js Only

FastAPI will **not** generate HTML map fragments server-side. Instead:
- FastAPI serves JSON and GeoJSON payloads via REST endpoints.
- `ui/static/js/map.js` handles all map rendering natively in the browser using Leaflet.js loaded from CDN.
- `ui/static/js/app.js` manages the WebSocket connection, job lifecycle state machine, and UI updates.

### 2. Directory Structure

```
ui/
+-- __init__.py
+-- web_app.py              # FastAPI APIRouter: mounts routes, templates, static
+-- templates/
|   +-- index.html          # Single-page dashboard (Jinja2)
+-- static/
    +-- css/
    |   +-- style.css       # Dark theme, responsive grid, custom components
    +-- js/
        +-- app.js          # WebSocket client, job state machine, DOM updates
        +-- map.js          # Leaflet.js init, markers, heatmap, GeoJSON layers
```

### 3. No Frontend Build Step

No Webpack, Vite, npm, or package.json. The frontend is vanilla:
- **Leaflet.js** loaded from CDN (`<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />` and `<script src="...">`).
- **Vanilla JS** (ES6 modules) for application logic.
- **CSS custom properties** for theming — easy dark/light mode toggle without a preprocessor.

This eliminates the Node.js dependency and keeps the project pure Python for developers.

### 4. Page Structure (index.html)

```
+------------------------------------------------------------------+
|  HEADER: Netryx Astra V2 logo + engine mode selector dropdown     |
+------------------------------------------------------------------+
|  LEFT PANEL (35%)              |  RIGHT PANEL (65%)               |
|  +----------------------------+  +-------------------------------+ |
|  | Image Upload (drag/drop)   |  | Leaflet.js Map               | |
|  | + thumbnail preview        |  |  - Dark tile layer           | |
|  |---------------------------|  |  - Search circle overlay     | |
|  | Coordinates: [lat] [lon]  |  |  - Candidate markers         | |
|  | Radius: [___] km          |  |  - Final result pin          | |
|  |---------------------------|  +-------------------------------+ |
|  | [Run Search]  [Cancel]    |                                     |
|  |---------------------------|                                     |
|  | Status: progress bar      |                                     |
|  |---------------------------|                                     |
|  | Results table             |                                     |
|  | # | Score | Lat/Lon      |                                     |
|  |---+-------+--------------|                                     |
|  | 1 | 452   | 55.75,37.61 |                                     |
|  | 2 | 310   | 55.76,37.62 |                                     |
|  +----------------------------+                                     |
+------------------------------------------------------------------+
|  FOOTER: Community Hub links, credits                             |
+------------------------------------------------------------------+
```

### 5. WebSocket Integration in app.js

```javascript
// app.js — Job State Machine
const states = {
  IDLE: 'idle',
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETE: 'complete',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

let currentJob = null;
let ws = null;

function connectWS(jobId) { ... }
function sendCancel() { ws.send(JSON.stringify({type: 'cancel'})); }
function onMessage(event) {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'progress': updateProgressBar(msg.current, msg.total); break;
    case 'match_update': map.addCandidateMarker(msg.lat, msg.lon, msg.inliers); break;
    case 'complete': map.setFinalPin(msg.result); showResults(msg.candidates); break;
    case 'error': showError(msg.message); break;
  }
}
```

### 6. Leaflet Map Integration in map.js

```javascript
// map.js — Leaflet Rendering Engine
const map = L.map('map', { ... });
L.tileLayer('https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png').addTo(map);

function addCandidateMarker(lat, lon, inliers) { ... }
function setFinalPin(result) {
  L.marker([result.lat, result.lon]).addTo(map)
    .bindPopup(`<b>Match: ${result.inliers} inliers</b><br>${result.lat}, ${result.lon}`);
}
function drawSearchCircle(center, radiusKm) { ... }
function loadCoverage(geoJSON) { ... }
```

## Consequences

- (+) Zero frontend build tooling — pure Python project with HTML/JS assets.
- (+) Full control over map rendering without server roundtrips for HTML fragments.
- (+) Easier debugging — open DevTools, inspect WebSocket frames directly.
- (+) No Folium API learning curve — standard Leaflet.js patterns.
- (-) More boilerplate JS compared to Gradio's auto-generated handlers.
- (-) Browser compatibility testing needed for WebSocket reconnection edge cases.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Folium server-side map generation | Every map update (500 candidate markers!) requires a server round-trip to regenerate HTML. Unworkable for real-time updates. |
| Gradio | Limited map interactivity, no WebSocket-level control, auto-generated UI doesn't match the target layout. |
| React + FastAPI backend | Adds Node.js build step, npm dependencies, JSX compilation. Overkill for a dashboard-focused tool with one main page. |
