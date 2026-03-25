# OpenHistoricalMap Integration Guide

**Historical Atlas Project**  
*MapLibre GL JS, Vector Tiles, Date Filtering, and Custom Overlays*  
*From OHM Tile Server to Production Map Application*

Version 1.0 — March 2026  
Companion to: Data Pipeline Architecture Document

---

## Table of Contents

1. [Overview and Architecture Decisions](#1-overview-and-architecture-decisions)
2. [OHM Tile Sources and Endpoints](#2-ohm-tile-sources-and-endpoints)
3. [OHM Stylesheets](#3-ohm-stylesheets)
4. [Basic Map Setup with MapLibre GL JS](#4-basic-map-setup-with-maplibre-gl-js)
5. [Date Filtering](#5-date-filtering)
6. [Text Rendering and Localization](#6-text-rendering-and-localization)
7. [Custom Entity Overlays](#7-custom-entity-overlays)
8. [Querying OHM Data](#8-querying-ohm-data)
9. [Alternative Embedding Methods](#9-alternative-embedding-methods)
10. [Common Issues and Troubleshooting](#10-common-issues-and-troubleshooting)
11. [Integration with the Data Pipeline](#11-integration-with-the-data-pipeline)
12. [Quick Reference](#12-quick-reference)

---

## 1. Overview and Architecture Decisions

OpenHistoricalMap (OHM) is the base map layer for the Historical Atlas project. OHM provides vector tiles containing global historical geographic data with temporal metadata, enabling time-filtered map rendering. This guide covers everything needed to integrate OHM into the project stack.

### 1.1 Why OHM

- **Vector tiles with temporal metadata:** Every feature includes `start_decdate` and `end_decdate` properties, allowing filtering by any date in history.
- **Public domain data:** OHM data is available under CC0 dedication, with no API key required for tile access.
- **MapLibre GL JS compatibility:** OHM publishes stylesheets conforming to the MapLibre Style Specification, which is the project's chosen map library.
- **No raster tiles:** OHM does not publish pre-rendered raster tiles (it isn't feasible to render every zoom level for every day in history), so vector tiles are the only option.

### 1.2 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Map renderer | MapLibre GL JS | OHM's preferred library; open source fork of Mapbox GL JS |
| Tile source | OHM vector tiles | Authoritative historical geodata with temporal filtering |
| Base stylesheet | OHM "Historic" style | Best general-purpose historical style; alternatives: Railway, Japanese Scroll, Woodblock |
| Date filtering | maplibre-gl-dates plugin | Official OHM plugin for filtering features by date |
| Custom overlays | Separate vector/GeoJSON sources | Project entities rendered as a layer on top of OHM base map |

---

## 2. OHM Tile Sources and Endpoints

OHM publishes four vector tilesets. All tiles are served as Protobuf (.pbf) files from the vtiles subdomain.

### 2.1 Available Tilesets

| Tileset | URL Template | Contents | License |
|---------|-------------|----------|---------|
| General | `https://vtiles.openhistoricalmap.org/maps/osm/{z}/{x}/{y}.pbf` | Places, boundaries (linear), transport, POIs, land use, natural features | Public domain |
| Boundary Polygons | `https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf` | Administrative boundary polygons. **Heavy tiles — filter aggressively.** | Public domain |
| Landmasses | `https://vtiles.openhistoricalmap.org/maps/ohm_land/{z}/{x}/{y}.pbf` | Land polygons from OSM coastlines. | ODbL |
| Waterbodies | `https://vtiles.openhistoricalmap.org/maps/ne/{z}/{x}/{y}.pbf` | Low-resolution lakes and reservoirs from Natural Earth. | Public domain |

> ⚠️ **Important:** OHM does not publish raster tiles. Do not attempt to use raster tile URL patterns (e.g., `.png`). The S3 404 errors in the console are caused by attempting to load raster tiles from a non-existent endpoint.

### 2.2 Temporal Properties

Every feature in OHM tiles includes two critical properties for date filtering:

- **`start_decdate`** — The start date as a decimal year (e.g., 1939.0 = January 1, 1939)
- **`end_decdate`** — The end date as a decimal year

These correspond to the `start_date=*` and `end_date=*` OSM tags, converted to decimal years. Filtering by these properties is what prevents anachronisms on the map (e.g., showing modern borders on a 1939 map).

### 2.3 Decimal Year Conversion

To convert a calendar date to a decimal year for manual filtering:

```javascript
function dateToDecimalYear(dateStr) {
  const d = new Date(dateStr);
  const year = d.getFullYear();
  const startOfYear = new Date(year, 0, 1);
  const startOfNext = new Date(year + 1, 0, 1);
  const yearLen = startOfNext - startOfYear;
  const elapsed = d - startOfYear;
  return year + elapsed / yearLen;
}

// Example: dateToDecimalYear('1939-09-01') => 1939.6657...
```

The `maplibre-gl-dates` plugin handles this conversion automatically when you pass ISO date strings.

---

## 3. OHM Stylesheets

### 3.1 Available Styles

OHM publishes four pre-built stylesheets conforming to the MapLibre Style Specification:

| Style | URL | Description |
|-------|-----|-------------|
| Historic | `https://www.openhistoricalmap.org/map-styles/main/main.json` | General-purpose historical style. **Recommended.** |
| Railway | `.../map-styles/railway/railway.json` | Focused on railway infrastructure. |
| Japanese Scroll | `.../map-styles/japanese_scroll/japanese_scroll.json` | Artistic scroll-style rendering. |
| Woodblock | `.../map-styles/woodblock/woodblock.json` | Woodblock print aesthetic. |

### 3.2 NPM Package

Stylesheets are also available via NPM:

```bash
npm install @openhistoricalmap/map-styles
```

### 3.3 Custom Stylesheets

For more control, write a custom stylesheet pointing to OHM vector tiles. Use [Maputnik](https://maputnik.github.io/) (a visual style editor) to design and export custom styles. The stylesheet must reference OHM tile sources and include temporal filters.

### 3.4 Known Font Limitations

OHM's "OpenHistorical Bold" font does not include glyphs for all Unicode ranges. Console warnings about missing glyph ranges (Cuneiform U+103xx, Ethiopic U+120xx–U+123xx) are expected and non-breaking. MapLibre falls back to local rendering for these characters.

To suppress these warnings, override the `glyphs` URL in the style to point to a more complete font stack (e.g., Noto Sans served from MapTiler or self-hosted).

---

## 4. Basic Map Setup with MapLibre GL JS

### 4.1 Required Dependencies

```bash
npm install maplibre-gl
npm install @openhistoricalmap/maplibre-gl-dates
```

### 4.2 Minimal Implementation

The simplest working OHM map with date filtering:

```javascript
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { filterByDate } from '@openhistoricalmap/maplibre-gl-dates';

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://www.openhistoricalmap.org/map-styles/main/main.json',
  center: [12.5, 41.9],  // Rome
  zoom: 5,
  attributionControl: {
    customAttribution:
      '<a href="https://www.openhistoricalmap.org/">OpenHistoricalMap</a>',
  },
});

map.once('styledata', () => {
  map.filterByDate('0117-01-01');  // Roman Empire at peak extent
});
```

### 4.3 React Component Implementation

For the project's React + Inertia.js stack:

```tsx
import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const OHM_STYLE =
  'https://www.openhistoricalmap.org/map-styles/main/main.json';

interface HistoricalMapProps {
  initialDate?: string;        // ISO date string
  center?: [number, number];   // [lng, lat]
  zoom?: number;
  onMapReady?: (map: maplibregl.Map) => void;
}

export function HistoricalMap({
  initialDate = '0117-01-01',
  center = [12.5, 41.9],
  zoom = 5,
  onMapReady,
}: HistoricalMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [currentDate, setCurrentDate] = useState(initialDate);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OHM_STYLE,
      center,
      zoom,
      attributionControl: {
        customAttribution:
          '<a href="https://www.openhistoricalmap.org/">OpenHistoricalMap</a>',
      },
    });

    map.once('styledata', () => {
      map.filterByDate(currentDate);
      onMapReady?.(map);
    });

    mapRef.current = map;

    return () => { map.remove(); };
  }, []);

  // Update date filter when currentDate changes
  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) {
      mapRef.current.filterByDate(currentDate);
    }
  }, [currentDate]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
  );
}
```

---

## 5. Date Filtering

### 5.1 The maplibre-gl-dates Plugin

This plugin adds the `filterByDate()` method to MapLibre's Map object. It modifies the style's filter expressions on every layer to show only features whose temporal range includes the specified date. Without this plugin, the map displays all features from all time periods simultaneously.

### 5.2 How Filtering Works

When `filterByDate('1939-09-01')` is called, the plugin:

1. Converts the ISO date string to a decimal year (1939.6657…)
2. Iterates over all layers in the style
3. Adds filter conditions: `start_decdate <= 1939.6657 AND end_decdate >= 1939.6657`
4. Features outside this temporal range are hidden from rendering

### 5.3 Building a Time Slider

The project's time slider (inspired by Civilization VI's timeline) should call `filterByDate()` as the user moves the slider. OHM provides the Timescope component for more sophisticated date selection, but for custom implementations:

```typescript
function handleDateChange(newDate: string) {
  setCurrentDate(newDate);
  if (mapRef.current?.isStyleLoaded()) {
    mapRef.current.filterByDate(newDate);
  }
}

// Example: slider spanning 500 BCE to 2000 CE
// Convert slider value (number) to ISO date string
function sliderValueToDate(value: number): string {
  const year = Math.floor(value);
  const frac = value - year;
  const dayOfYear = Math.floor(frac * 365);
  const d = new Date(year, 0, 1 + dayOfYear);
  return d.toISOString().split('T')[0];
}
```

> ⚠️ **Performance:** Calling `filterByDate()` triggers a re-render of all layers. Debounce or throttle the call when using a continuously draggable slider to avoid performance issues.

---

## 6. Text Rendering and Localization

### 6.1 Right-to-Left Text

To correctly display Arabic and Hebrew labels on the map, install the RTL text plugin:

```javascript
maplibregl.setRTLTextPlugin(
  'https://cdn.maptiler.com/mapbox-gl-rtl-text/v0.2.3/mapbox-gl-rtl-text.min.js',
  true  // lazy load
);
```

### 6.2 Label Localization

OHM tiles contain localized names in languages with 50+ occurrences of `name:*` tags. To localize labels to the user's preferred language, install the mapbox-gl-language plugin:

```javascript
import MapboxLanguage from '@mapbox/mapbox-gl-language';

map.addControl(new MapboxLanguage({
  defaultLanguage: 'en',
}));
```

---

## 7. Custom Entity Overlays

The Historical Atlas project adds its own entity markers, boundary annotations, and relationship lines on top of the OHM base map. These are separate sources and layers added to MapLibre after the OHM style loads.

### 7.1 Adding a GeoJSON Entity Layer

```javascript
map.on('load', () => {
  // Add entity data source
  map.addSource('atlas-entities', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: []  // populated from API
    }
  });

  // Point entities (battles, cities, etc.)
  map.addLayer({
    id: 'entity-points',
    type: 'circle',
    source: 'atlas-entities',
    filter: ['==', '$type', 'Point'],
    paint: {
      'circle-radius': 6,
      'circle-color': ['match', ['get', 'entity_type'],
        'battle', '#E74C3C',
        'city', '#3498DB',
        'person_birth', '#2ECC71',
        '#95A5A6'  // default
      ],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#FFFFFF'
    }
  });
});
```

### 7.2 Adding Custom Vector Tile Sources

If the project serves its own entity data as vector tiles (e.g., from PostGIS via pg_tileserv or Martin), add them as a separate source:

```javascript
map.addSource('atlas-vector', {
  type: 'vector',
  tiles: [
    'https://your-tile-server.com/entities/{z}/{x}/{y}.pbf'
  ],
  minzoom: 2,
  maxzoom: 14
});
```

### 7.3 Bezier Curve Annotations

For the custom annotation layer (relationship arrows, trade routes, migration paths), use MapLibre's line layers with GeoJSON LineString geometries. Bezier curves must be pre-interpolated into point sequences before being passed to MapLibre, as MapLibre does not natively support bezier curves.

---

## 8. Querying OHM Data

### 8.1 Overpass API

OHM provides an Overpass API instance for querying the database with specific criteria. The endpoint accepts OverpassQL queries.

**Endpoint:** `https://overpass-api.openhistoricalmap.org/api/interpreter`

Useful for extracting specific features for batch processing in the data pipeline (Stage 1 ingestion).

### 8.2 Nominatim

OHM's Nominatim instance allows searching for features by name. This is useful for the geocoding cascade (Stage 3 of the data pipeline) as the first-priority geocoder.

**Endpoint:** `https://nominatim.openhistoricalmap.org/`

### 8.3 QLever (SPARQL)

QLever provides SPARQL queries over the OHM dataset, with federation support for OpenStreetMap and Wikidata. Results can be returned as tables, maps, or heatmaps.

### 8.4 Planet Files

For bulk data processing, full OHM database dumps are available in `planet.osm` format on Amazon S3. New planet files are generated daily; full revision history files are generated weekly.

---

## 9. Alternative Embedding Methods

### 9.1 iframe Embed

The simplest integration method, useful for previews or non-interactive displays:

```html
<iframe
  src="https://embed.openhistoricalmap.org/#map=5/41.9/12.5&date=0117-01-01"
  width="100%"
  height="500"
  frameborder="0"
></iframe>
```

Limited interactivity — no programmatic control over layers, events, or custom overlays.

### 9.2 Leaflet Integration

If using Leaflet (not recommended for this project), MapLibre GL Leaflet bridges the two libraries:

```javascript
import L from 'leaflet';
import '@maplibre/maplibre-gl-leaflet';

const map = L.map('map').setView([41.9, 12.5], 5);

const gl = L.maplibreGL({
  style: 'https://www.openhistoricalmap.org/map-styles/main/main.json',
}).addTo(map);

const mlMap = gl.getMaplibreMap();
mlMap.once('styledata', () => {
  mlMap.filterByDate('0117-01-01');
});
```

---

## 10. Common Issues and Troubleshooting

### 10.1 Console Errors Reference

| Error | Cause | Solution |
|-------|-------|----------|
| `Expected value to be of type number, but found string` | OHM tile data type mismatch in vector tile properties | Not fixable on your end. OHM data quality issue. Non-breaking — tiles still render. |
| 404 on `.pbf` font files (OpenHistorical Bold) | Missing glyph ranges for non-Latin scripts (Cuneiform, Ethiopic) | Override glyphs URL to a complete font stack, or ignore — MapLibre falls back to local rendering. |
| 404 on `.png` tile URLs | Attempting to load raster tiles — OHM does not serve raster tiles | Remove any raster tile sources. Use only vector tile (.pbf) URLs. |
| All periods shown simultaneously | `filterByDate()` not called or called before style loads | Ensure `filterByDate()` is called inside the `styledata` or `load` event callback. |
| Blank map with no features | Date filter too restrictive or OHM has no data for that region/period | Check date format (ISO string). Verify OHM has data coverage for the area. |

### 10.2 Performance Considerations

- **Boundary polygon tiles are heavy.** The `ohm_admin` tileset should be filtered aggressively in the stylesheet. Only request boundary polygons for the specific entities you need.
- **Debounce `filterByDate()`.** When using a time slider, throttle calls to avoid re-rendering on every pixel of slider movement. 100–200ms debounce is recommended.
- **Limit concurrent tile requests.** MapLibre's default of 6 concurrent requests per domain is usually sufficient. If the map feels slow, ensure no other code is making excessive requests to the OHM tile server.

### 10.3 Legal and Attribution

OHM data is public domain under CC0 dedication. As a courtesy, credit OpenHistoricalMap contributors on or near the map. The recommended attribution string:

```html
<a href="https://www.openhistoricalmap.org/">OpenHistoricalMap</a>
```

---

## 11. Integration with the Data Pipeline

### 11.1 Stage 1: OHM as Source Data

OHM's Overpass API and Planet files can serve as source documents for the data pipeline. Historical boundaries, place names, and temporal metadata in OHM can be ingested alongside academic PDFs, Wikipedia articles, and structured databases.

### 11.2 Stage 3: OHM Nominatim in Geocoding Cascade

OHM Nominatim is the first-priority geocoder in the cascade, searched before Wikidata, GeoNames, and Pleiades. A match from OHM Nominatim is the strongest signal because it confirms the place existed at the relevant time period with temporal metadata.

### 11.3 Stage 8: Human Review Interface

The review interface uses the OHM base map as the background for entity review. The reviewer sees the entity marker on the OHM map at the relevant time period, with the base map filtered to show the historical context (borders, cities, roads) as they existed at that time.

This is implemented using the React component from Section 4.3, with the `initialDate` prop set to the entity's `temporal_start` value and the `center` prop set to the entity's coordinates.

---

## 12. Quick Reference

### 12.1 Essential URLs

| Resource | URL |
|----------|-----|
| OHM Homepage | `https://www.openhistoricalmap.org/` |
| Main Style JSON | `https://www.openhistoricalmap.org/map-styles/main/main.json` |
| General Vector Tiles | `https://vtiles.openhistoricalmap.org/maps/osm/{z}/{x}/{y}.pbf` |
| Boundary Polygons | `https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf` |
| Landmasses | `https://vtiles.openhistoricalmap.org/maps/ohm_land/{z}/{x}/{y}.pbf` |
| Waterbodies | `https://vtiles.openhistoricalmap.org/maps/ne/{z}/{x}/{y}.pbf` |
| Nominatim | `https://nominatim.openhistoricalmap.org/` |
| Overpass API | `https://overpass-api.openhistoricalmap.org/api/interpreter` |
| NPM Styles | `@openhistoricalmap/map-styles` |
| NPM Date Filter | `@openhistoricalmap/maplibre-gl-dates` |

### 12.2 NPM Packages

| Package | Purpose |
|---------|---------|
| `maplibre-gl` | Map renderer (required) |
| `@openhistoricalmap/maplibre-gl-dates` | Date filtering plugin (required) |
| `@openhistoricalmap/map-styles` | Pre-built OHM stylesheets (optional) |
| `@mapbox/mapbox-gl-language` | Label localization (optional) |
| `@maplibre/maplibre-gl-leaflet` | Leaflet bridge (only if using Leaflet) |

---

*End of Document*