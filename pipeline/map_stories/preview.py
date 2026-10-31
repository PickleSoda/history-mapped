"""Render a map story's steps over a topographic basemap, as PNG screenshots.

    python -m pipeline.map_stories preview api/resources/map-stories/battle-of-cannae.json
    python -m pipeline.map_stories preview <story.json> --step 3

Writes output/map-stories/preview/<slug>/{grid.png | step-NN.png} with
headless Chrome + Leaflet + OpenTopoMap tiles (contours, rivers, villages), so
an author can check that formations sit where the sources put them — beside
the river, on the ridge — before the story reaches the atlas. Formations are
drawn with the same geometry rules as the atlas (web/src/lib/map-story).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pipeline.map_stories.validate import resolve_steps

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "output" / "map-stories" / "preview"

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body{margin:0;font:13px/1.3 system-ui,sans-serif;background:#f4f1ea;color:#222}
  .grid{display:grid;grid-template-columns:repeat(var(--cols),__W__px);gap:10px;padding:10px}
  .cell{background:#fff;border:1px solid #ccc}
  .cap{padding:5px 8px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cap span{font-weight:400;color:#666}
  .map{width:__W__px;height:__H__px}
  .lbl{background:rgba(255,255,255,.85);border:0;box-shadow:none;padding:0 3px;font-size:11px;font-weight:600;white-space:nowrap}
  .lbl:before{display:none}
  .ter{background:transparent;border:0;box-shadow:none;font-size:11px;font-style:italic;color:#14532d;white-space:nowrap;text-shadow:0 0 3px #fff,0 0 3px #fff}
  .ter:before{display:none}
  .note{background:#fff7d6;border:1px solid #b45309;padding:1px 4px;font-size:11px;white-space:nowrap}
  .note:before{display:none}
  .legend{padding:6px 10px;font-size:12px}
</style></head><body>
<div class="legend" id="legend"></div>
<div class="grid" id="grid" style="--cols:__COLS__"></div>
<script>
const DOC = __DOC__;
const SNAPSHOTS = __SNAPSHOTS__;
const ONLY = __ONLY__;
const R = 6371008.8, rad = Math.PI / 180;

function dest(p, brg, m) {
  const la1 = p[1]*rad, lo1 = p[0]*rad, b = brg*rad, d = m/R;
  const la2 = Math.asin(Math.sin(la1)*Math.cos(d) + Math.cos(la1)*Math.sin(d)*Math.cos(b));
  const lo2 = lo1 + Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(la1), Math.cos(d)-Math.sin(la1)*Math.sin(la2));
  return [lo2/rad, la2/rad];
}
function brg(a, b) {
  const la1=a[1]*rad, la2=b[1]*rad, dl=(b[0]-a[0])*rad;
  return (Math.atan2(Math.sin(dl)*Math.cos(la2), Math.cos(la1)*Math.sin(la2)-Math.sin(la1)*Math.cos(la2)*Math.cos(dl))/rad+360)%360;
}
// A point `fwd` metres toward the formation's front and `right` metres to its right.
function at(c, facing, fwd, right) { return dest(dest(c, facing, fwd), facing+90, right); }

function formation(pl, kind) {
  const c = pl.at, f = pl.facing ?? 0, w = pl.width ?? 300, d = pl.depth ?? Math.max(20, Math.min(w/4, 120));
  const shape = pl.shape ?? 'block';
  if (shape === 'wedge') return [at(c,f,d/2,0), at(c,f,-d/2,w/2), at(c,f,-d/2,-w/2)];
  if (shape === 'circle') {
    const ring = [];
    for (let i = 0; i < 24; i++) { const a = i/24*2*Math.PI; ring.push(at(c, f, Math.cos(a)*d/2, Math.sin(a)*w/2)); }
    return ring;
  }
  if (shape === 'crescent') {
    const bulge = pl.curve ?? w*0.18, n = 12, front = [], back = [];
    for (let i = 0; i <= n; i++) {
      const x = -w/2 + w*i/n, k = bulge*(1 - Math.pow(2*x/w, 2)) - bulge/2;
      front.push(at(c, f, d/2 + k, x)); back.push(at(c, f, -d/2 + k, x));
    }
    return front.concat(back.reverse());
  }
  return [at(c,f,d/2,-w/2), at(c,f,d/2,w/2), at(c,f,-d/2,w/2), at(c,f,-d/2,-w/2)];
}

const SIDE = Object.fromEntries(DOC.sides.map(s => [s.id, s]));
const UNIT = Object.fromEntries(DOC.units.map(u => [u.id, u]));
const ABBR = {infantry:'INF',heavy_infantry:'HI',light_infantry:'LI',pikemen:'PIKE',archers:'ARCH',slingers:'SLNG',crossbowmen:'XBOW',musketeers:'MUSK',cavalry:'CAV',heavy_cavalry:'HC',light_cavalry:'LC',horse_archers:'HA',chariots:'CHAR',elephants:'ELE',camels:'CAM',artillery:'ART',siege_engine:'SIEGE',warship:'SHIP',transport:'TRNS',commander:'★',camp:'CAMP',baggage:'BAG'};
const TER = {river:['#2563eb',3],stream:['#3b82f6',2],road:['#78716c',2],ridge:['#92400e',3],wall:['#44403c',3],coast:['#1e3a8a',2],
  hill:['#a16207',.18],woods:['#15803d',.25],marsh:['#0f766e',.22],lake:['#2563eb',.35],sea:['#1d4ed8',.25],island:['#a3a3a3',.3],fortification:['#57534e',.35],camp:['#78716c',.25],field:['#ca8a04',.12]};
const MOVE_DASH = {retreat:'8 6',rout:'4 6',feint:'10 5',march:'2 6',fire:'1 5'};

document.getElementById('legend').innerHTML = `<b>${DOC.title}</b> — ${DOC.date_label} &nbsp; ` +
  DOC.sides.map(s => `<span style="color:${s.color}">■</span> ${s.name}`).join(' &nbsp; ');

function draw(idx) {
  const step = DOC.steps[idx], snap = SNAPSHOTS[idx];
  const cell = document.createElement('div'); cell.className = 'cell';
  cell.innerHTML = `<div class="cap">${idx+1}. ${step.title} <span>${step.time ?? ''}</span></div><div class="map"></div>`;
  document.getElementById('grid').appendChild(cell);
  const map = L.map(cell.querySelector('.map'), {zoomControl:false, attributionControl:false, zoomSnap:0, fadeAnimation:false, zoomAnimation:false});
  L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {maxZoom:17, subdomains:'abc'}).addTo(map);
  const ll = p => [p[1], p[0]];
  const pts = [];
  for (const t of DOC.terrain ?? []) {
    const [col, wt] = TER[t.kind] ?? ['#555', 2];
    if (t.line) L.polyline(t.line.map(ll), {color:col, weight:wt, opacity:.85}).addTo(map).bindTooltip(t.label ?? '', {permanent:!!t.label, className:'ter', direction:'center'});
    if (t.area) L.polygon(t.area.map(ll), {color:col, weight:1, fillColor:col, fillOpacity:wt}).addTo(map).bindTooltip(t.label ?? '', {permanent:!!t.label, className:'ter', direction:'center'});
    if (t.at) L.circleMarker(ll(t.at), {radius:4, color:'#111', fillColor:'#fff', fillOpacity:1, weight:1.5}).addTo(map).bindTooltip(t.label ?? '', {permanent:!!t.label, className:'ter', direction:'right'});
  }
  for (const mv of step.moves ?? []) {
    const side = SIDE[mv.side ?? UNIT[mv.unit]?.side]; const col = side?.color ?? '#333';
    L.polyline(mv.path.map(ll), {color:col, weight: mv.type === 'charge' ? 5 : 3, opacity:.9, dashArray: MOVE_DASH[mv.type]}).addTo(map);
    const a = mv.path[mv.path.length-2], b = mv.path[mv.path.length-1], h = brg(a, b);
    L.polygon([b, dest(b, h+150, 120), dest(b, h-150, 120)].map(ll), {color:col, weight:1, fillColor:col, fillOpacity:.95}).addTo(map);
    mv.path.forEach(p => pts.push(p));
  }
  for (const [uid, pl] of Object.entries(snap)) {
    const u = UNIT[uid]; if (!u || !pl.at) continue; const s = SIDE[u.side];
    if (pl.with && snap[pl.with]) { const h = snap[pl.with]; pl.at = dest(h.at, (h.facing ?? 0) + 180, (h.depth ?? 60)/2 + 50); }
    pts.push(pl.at);
    const faded = pl.state === 'routed' || pl.state === 'destroyed';
    if (['commander','camp','baggage'].includes(u.kind)) {
      L.circleMarker(ll(pl.at), {radius: u.kind === 'commander' ? 6 : 5, color:'#111', weight:1.5, fillColor:s.color, fillOpacity:1}).addTo(map)
        .bindTooltip(`${ABBR[u.kind]} ${pl.label ?? u.label}`, {permanent:true, className:'lbl', direction:'right', offset:[6,0]});
      continue;
    }
    const poly = formation(pl, u.kind);
    poly.forEach(p => pts.push(p));
    L.polygon(poly.map(ll), {color: faded ? '#555' : '#111', weight: pl.state === 'engaged' ? 2.5 : 1, dashArray: faded ? '4 4' : null,
      fillColor: s.color, fillOpacity: pl.state === 'destroyed' ? .15 : faded ? .35 : .8}).addTo(map);
    const front = dest(pl.at, pl.facing ?? 0, (pl.depth ?? 60)/2 + 10);
    L.polyline([pl.at, front].map(ll), {color:'#fff', weight:1.5, opacity:.9}).addTo(map);
    L.marker(ll(pl.at), {opacity:0}).addTo(map).bindTooltip(`${ABBR[u.kind] ?? u.kind} ${pl.label ?? u.label}${pl.state && pl.state !== 'ready' ? ' ('+pl.state+')' : ''}`, {permanent:true, className:'lbl', direction:'center'});
  }
  for (const n of step.notes ?? []) {
    L.circleMarker(ll(n.at), {radius:3, color:'#b45309', fillColor:'#b45309', fillOpacity:1}).addTo(map)
      .bindTooltip(n.text, {permanent:true, className:'note', direction:'top', offset:[0,-4]});
  }
  if (step.camera) map.setView(ll(step.camera.center), step.camera.zoom + 1);
  else if (pts.length) map.fitBounds(L.latLngBounds(pts.map(ll)), {padding:[24,24], maxZoom:16});
  else map.setView([0,0], 2);
}
const order = ONLY === null ? DOC.steps.map((_, i) => i) : [ONLY];
order.forEach(draw);
</script></body></html>
"""


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("preview needs Chrome or Chromium on PATH")


def render(doc: dict, step: int | None = None, width: int = 760, height: int = 560) -> Path:
    slug = doc.get("slug", "story")
    out_dir = OUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(doc.get("steps", []))
    if step is not None and not 0 <= step < n:
        raise SystemExit(f"--step must be 0..{n - 1}")
    cols = 1 if step is not None else 2
    count = 1 if step is not None else n
    rows = (count + cols - 1) // cols
    html = (
        PAGE.replace("__DOC__", json.dumps(doc))
        .replace("__SNAPSHOTS__", json.dumps(resolve_steps(doc)))
        .replace("__ONLY__", "null" if step is None else str(step))
        .replace("__COLS__", str(cols))
        .replace("__W__", str(width))
        .replace("__H__", str(height))
    )
    page = out_dir / "preview.html"
    page.write_text(html)
    png = out_dir / ("grid.png" if step is None else f"step-{step + 1:02d}.png")
    total_w = cols * (width + 12) + 12
    total_h = rows * (height + 40) + 50
    subprocess.run(
        [
            chrome(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={out_dir / '.chrome'}",
            f"--window-size={total_w},{total_h}",
            "--virtual-time-budget=20000",
            f"--screenshot={png}",
            page.as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return png
