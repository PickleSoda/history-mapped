// =====================================================================
// history-mapped — SLA load test (k6)
//
// Reproduces the three map-read cases derived in the final report
// (§8 Performance) plus entity-detail reads and fuzzy search, with
// thresholds set to the report's SLA targets. Passing run = the numbers
// to put into the report's Table "Performance ranges".
//
//   BASE_URL    target origin, e.g. https://droplet.example.com  (required)
//   TARGET_VUS  peak virtual users for the ramp        (default 30)
//   DURATION    length of the peak plateau             (default 3m)
//
//   k6 run -e BASE_URL=https://your-droplet scripts/loadtest/sla-test.js
//
// IMPORTANT: run against the droplet origin directly. Do NOT point this
// at a Cloudflare-proxied hostname — it violates CF's terms and their
// cache distorts the numbers.
// =====================================================================
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL;
if (!BASE) throw new Error('Set BASE_URL, e.g. -e BASE_URL=https://your-droplet');

const PEAK = Number(__ENV.TARGET_VUS || 30);
const PLATEAU = __ENV.DURATION || '3m';

// Ramp used by every scenario (scaled per scenario below):
// warm-up -> plateau at peak -> ramp-down.
const ramp = (share) => [
  { duration: '1m', target: Math.max(1, Math.round(PEAK * share * 0.3)) },
  { duration: PLATEAU, target: Math.max(1, Math.round(PEAK * share)) },
  { duration: '30s', target: 0 },
];

export const options = {
  scenarios: {
    map_warm:    { executor: 'ramping-vus', exec: 'mapWarm',    stages: ramp(0.2) },
    map_average: { executor: 'ramping-vus', exec: 'mapAverage', stages: ramp(0.3) },
    map_worst:   { executor: 'ramping-vus', exec: 'mapWorst',   stages: ramp(0.2) },
    detail:      { executor: 'ramping-vus', exec: 'detail',     stages: ramp(0.2) },
    search:      { executor: 'ramping-vus', exec: 'search',     stages: ramp(0.1) },
  },
  thresholds: {
    // = report SLA targets (Table "Performance ranges")
    'http_req_duration{name:map-warm}':    ['p(95)<800'],
    'http_req_duration{name:map-average}': ['p(95)<800'],
    'http_req_duration{name:map-worst}':   ['p(95)<800'],
    'http_req_duration{name:entity-detail}': ['p(95)<200'],
    'http_req_duration{name:search}':      ['p(95)<300'],
    http_req_failed: ['rate<0.005'],       // 99.5% availability target
  },
  // keep result cardinality sane
  summaryTrendStats: ['min', 'med', 'avg', 'p(95)', 'p(99)', 'max'],
};

// A few plausible mid-zoom viewports (Mediterranean, Europe, Near East,
// Egypt/Nile, India, China) — the "typical interactive pan/zoom" case.
const REGIONS = [
  { minLng: -10, minLat: 30, maxLng: 30, maxLat: 46 },
  { minLng: -5, minLat: 42, maxLng: 25, maxLat: 55 },
  { minLng: 25, minLat: 30, maxLng: 50, maxLat: 42 },
  { minLng: 28, minLat: 22, maxLng: 36, maxLat: 32 },
  { minLng: 68, minLat: 8, maxLng: 90, maxLat: 30 },
  { minLng: 100, minLat: 20, maxLng: 122, maxLat: 42 },
];

const YEARS = () => -800 + Math.floor(Math.random() * 2800); // 800 BCE..2000 CE
const jitter = (v, amount) => v + (Math.random() - 0.5) * amount;

function mapUrl(b, year, zoom) {
  return `${BASE}/api/v1/entities/map` +
    `?bbox_min_lng=${b.minLng.toFixed(3)}&bbox_min_lat=${b.minLat.toFixed(3)}` +
    `&bbox_max_lng=${b.maxLng.toFixed(3)}&bbox_max_lat=${b.maxLat.toFixed(3)}` +
    `&year=${year}&zoom_level=${zoom}`;
}

export function setup() {
  // Grab real entity ids for the detail scenario, and a warm-path ETag.
  const list = http.get(`${BASE}/api/v1/entities?per_page=50`);
  check(list, { 'setup: list 200': (r) => r.status === 200 });
  const ids = (list.json('data') || []).map((e) => e.id).filter(Boolean);
  if (ids.length === 0) throw new Error('setup: no entities returned — is the dataset seeded?');

  const warm = { region: REGIONS[0], year: 0, zoom: 6 };
  const first = http.get(mapUrl(warm.region, warm.year, warm.zoom));
  check(first, { 'setup: map 200': (r) => r.status === 200 });
  return { ids, warm, etag: first.headers['Etag'] || first.headers['ETag'] || '' };
}

// --- Best case: identical request, warm cache, conditional revalidation ---
export function mapWarm(data) {
  const res = http.get(mapUrl(data.warm.region, data.warm.year, data.warm.zoom), {
    headers: data.etag ? { 'If-None-Match': data.etag } : {},
    tags: { name: 'map-warm' },
  });
  check(res, { 'map-warm 200/304': (r) => r.status === 200 || r.status === 304 });
  sleep(0.5 + Math.random());
}

// --- Average case: mid-zoom pan/zoom over plausible viewports ---
export function mapAverage() {
  const r = REGIONS[Math.floor(Math.random() * REGIONS.length)];
  const b = {
    minLng: jitter(r.minLng, 4), minLat: jitter(r.minLat, 2),
    maxLng: jitter(r.maxLng, 4), maxLat: jitter(r.maxLat, 2),
  };
  const res = http.get(mapUrl(b, YEARS(), 5 + Math.floor(Math.random() * 3)),
                       { tags: { name: 'map-average' } });
  check(res, { 'map-average 200': (r_) => r_.status === 200 });
  sleep(0.5 + Math.random());
}

// --- Worst case: huge low-zoom bbox, cold cache, antimeridian half the time ---
export function mapWorst() {
  const crossAM = Math.random() < 0.5;
  const b = crossAM
    // 150E..210 (wraps to -150) -> server splits the envelope at ±180
    ? { minLng: 150, minLat: -50 + Math.random() * 5, maxLng: 210, maxLat: 55 + Math.random() * 5 }
    : { minLng: -170 + Math.random() * 5, minLat: -55, maxLng: 170 + Math.random() * 5, maxLat: 65 };
  // random year + jittered bbox => every request is a distinct cache key
  const res = http.get(mapUrl(b, YEARS(), 2), { tags: { name: 'map-worst' } });
  check(res, { 'map-worst 200': (r) => r.status === 200 });
  sleep(1 + Math.random());
}

// --- Entity detail reads over real ids ---
export function detail(data) {
  const id = data.ids[Math.floor(Math.random() * data.ids.length)];
  const res = http.get(`${BASE}/api/v1/entities/${id}`, { tags: { name: 'entity-detail' } });
  check(res, { 'detail 200': (r) => r.status === 200 });
  sleep(0.3 + Math.random() * 0.7);
}

// --- Fuzzy search ---
const TERMS = ['rome', 'egypt', 'alexandr', 'byzant', 'carthage', 'mongol',
               'silk', 'persia', 'athen', 'karnak'];
export function search() {
  const q = TERMS[Math.floor(Math.random() * TERMS.length)];
  const res = http.get(`${BASE}/api/v1/entities?search=${q}&per_page=20`,
                       { tags: { name: 'search' } });
  check(res, { 'search 200': (r) => r.status === 200 });
  sleep(0.5 + Math.random());
}
