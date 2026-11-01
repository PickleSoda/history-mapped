"""Render a map story over a topographic basemap as PNG screenshots.

    python -m pipeline.map_stories preview <story.json>                 # contact sheet: every step, 360×240 each
    python -m pipeline.map_stories preview <story.json> --step hougoumont  # one step (id or 1-based number), 900×600
    python -m pipeline.map_stories preview <story.json> --all-steps     # every step at 760×560 (large)

Writes output/map-stories/preview/<slug>/{contact.png | step-NN.png | grid.png}
with headless Chrome + Leaflet + OpenTopoMap tiles (contours, rivers,
villages), so an author can see that formations sit where the sources put
them. Formations follow the atlas's geometry rules (web/src/lib/map-story).
Schema-2 fields the preview doesn't draw are ignored; beats are folded into
their step (the final frame is drawn); `conjectural` items are dashed and
`frame: false` units are left out of the framing. Schema-3 features are drawn
in each step's resolved state: routes (width by `value_n`, dashed when
disrupted), regions (shaded by `intensity`), point features (circles sized by
`value_n`); inactive features are left out, and `area_from_entity` (which needs
the atlas DB) is not drawn.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from pipeline.map_stories.lint import VIEWPORT, flatten_beats
from pipeline.map_stories.schema import POINT_UNIT_KINDS
from pipeline.map_stories.validate import normalise, resolve_features, resolve_steps

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "output" / "map-stories" / "preview"

#: mode → (cell width, cell height, columns or None for automatic, small labels)
MODES = {"contact": (360, 240, None, True), "step": (900, 600, 1, False), "all": (760, 560, 2, False)}

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body{margin:0;font:13px/1.3 system-ui,sans-serif;background:#f4f1ea;color:#222}
  .grid{display:grid;grid-template-columns:repeat(var(--cols),__W__px);gap:__GAP__px;padding:__GAP__px}
  .cell{background:#fff;border:1px solid #ccc}
  .cap{padding:3px 6px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cap span{font-weight:400;color:#666}
  .map{width:__W__px;height:__H__px}
  .lbl{background:rgba(255,255,255,.85);border:0;box-shadow:none;padding:0 3px;font-size:11px;font-weight:600;white-space:nowrap}
  .lbl:before,.ter:before,.note:before{display:none}
  .ter{background:transparent;border:0;box-shadow:none;font-size:11px;font-style:italic;color:#14532d;white-space:nowrap;text-shadow:0 0 3px #fff,0 0 3px #fff}
  .note{background:#fff7d6;border:1px solid #b45309;padding:1px 4px;font-size:11px;white-space:nowrap}
  .legend{padding:4px 10px;font-size:12px}
  body.small .cap{font-size:11px;padding:2px 5px}
  body.small .lbl{font-size:8.5px;padding:0 2px;background:rgba(255,255,255,.7)}
  body.small .ter{font-size:8.5px}
  body.small .note{font-size:8.5px;padding:0 2px}
</style></head><body class="__BODY__">
<div class="legend" id="legend"></div>
<div class="grid" id="grid" style="--cols:__COLS__"></div>
<script>
const DOC = __DOC__;
const SNAPSHOTS = __SNAPSHOTS__;
const FEATURES = __FEATURES__;
const ORDER = __ORDER__;
const POINT_KINDS = __POINT_KINDS__;
const ZOOM_SHIFT = __ZOOM_SHIFT__, HEAD_PX = __HEAD_PX__, PAD = __PAD__, SMALL = __SMALL__;
const cut = (t, n) => !SMALL || t.length <= n ? t : t.slice(0, n - 1) + '…';
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

function formation(pl) {
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

const SIDE = Object.fromEntries((DOC.sides ?? []).map(s => [s.id, s]));
const UNIT = Object.fromEntries((DOC.units ?? []).map(u => [u.id, u]));
const ABBR = {army:'ARMY',fleet:'FLEET',caravan:'CVN',merchant_ship:'⛵',expedition:'EXP',group:'GRP',infantry:'INF',heavy_infantry:'HI',light_infantry:'LI',pikemen:'PIKE',archers:'ARCH',slingers:'SLNG',crossbowmen:'XBOW',musketeers:'MUSK',cavalry:'CAV',heavy_cavalry:'HC',light_cavalry:'LC',horse_archers:'HA',chariots:'CHAR',elephants:'ELE',camels:'CAM',artillery:'ART',siege_engine:'SIEGE',warship:'SHIP',transport:'TRNS',commander:'★',camp:'CAMP',baggage:'BAG',standard:'⚑',ship:'⛵'};
const TER = {river:['#2563eb',3],stream:['#3b82f6',2],road:['#78716c',2],ridge:['#92400e',3],wall:['#44403c',3],coast:['#1e3a8a',2],
  hill:['#a16207',.18],woods:['#15803d',.25],marsh:['#0f766e',.22],lake:['#2563eb',.35],sea:['#1d4ed8',.25],island:['#a3a3a3',.3],fortification:['#57534e',.35],camp:['#78716c',.25],field:['#ca8a04',.12]};
const MOVE_DASH = {retreat:'8 6',rout:'4 6',feint:'10 5',march:'2 6',fire:'1 5',back_water:'8 6',blockade:'2 8',sail:'8 4',trade:'3 5',migrate:'10 4',explore:'2 4',spread:'1 4'};
// Schema-3 feature colours (a preview palette: the atlas has its own).
const ROUTE_COL = {trade:'#b45309',voyage:'#0e7490',migration:'#7c3aed',pilgrimage:'#047857',campaign:'#b91c1c',road:'#57534e'};
const REGION_COL = {spread:'#991b1b',extent:'#1d4ed8',influence:'#7c3aed',affected:'#c2410c',front:'#b91c1c'};
const POINT_COL = {city:'#1f2937',port:'#0e7490',market:'#b45309',mine:'#57534e',outbreak:'#991b1b',site:'#4b5563'};
const MAXV = {};
for (const fr of FEATURES) for (const f of Object.values(fr)) if (f.value_n) MAXV[f.kind] = Math.max(MAXV[f.kind] ?? 0, f.value_n);
const rings = a => !Array.isArray(a) || !a.length ? [] : Array.isArray(a[0][0]) ? a : [a];
const when = d => !d ? '' : [d.day, ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][(d.month ?? 0) - 1], d.year < 0 ? (-d.year)+' BC' : d.year].filter(x => x).join(' ') + (d.end ? '–' + when(d.end) : '');
const FADED = ['routed','destroyed','sunk','captured','killed'];

document.getElementById('legend').innerHTML = `<b>${DOC.title}</b> — ${DOC.date_label ?? ''} &nbsp; ` +
  (DOC.sides ?? []).map(s => `<span style="color:${s.color}">■</span> ${s.name}`).join(' &nbsp; ') + ' &nbsp; ' +
  (DOC.legend ?? []).map(l => `<span style="color:${l.swatch}">${l.style === 'line' ? '━' : l.style === 'dot' ? '●' : '■'}</span> ${l.label}`).join(' &nbsp; ') +
  ' &nbsp; <span style="color:#666">dashed = conjectural / routed / disrupted</span>';

function draw(idx) {
  const step = DOC.steps[idx], snap = SNAPSHOTS[idx];
  const cell = document.createElement('div'); cell.className = 'cell';
  cell.innerHTML = `<div class="cap">${idx+1}. ${step.id} <span>${step.time ?? when(step.date)}${step.entry != null ? ' · entry ' + step.entry : ''}</span></div><div class="map"></div>`;
  document.getElementById('grid').appendChild(cell);
  const map = L.map(cell.querySelector('.map'), {zoomControl:false, attributionControl:false, zoomSnap:0, fadeAnimation:false, zoomAnimation:false});
  L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {maxZoom:17, subdomains:'abc'}).addTo(map);
  const ll = p => [p[1], p[0]];
  const pts = [], heads = [];
  for (const t of Object.values(FEATURES[idx] ?? {})) {
    if (t.active === false) continue;
    const dash = t.conjectural ? '6 5' : t.state === 'disrupted' || t.state === 'abandoned' ? '3 5' : null;
    const shown = t.value_label ? `${t.label ?? ''} ${t.value_label}`.trim() : t.label;
    const tip = (lyr, dir) => shown && (!SMALL || t.value_label || t.kind === 'outbreak' || t.kind === 'port' || t.kind === 'market' || t.kind === 'city') ? lyr.bindTooltip(cut(shown, 22), {permanent:true, className:'ter', direction:dir}) : lyr;
    const sideCol = SIDE[t.side]?.color;
    if (t.kind === 'route' && t.line) {
      const col = sideCol ?? ROUTE_COL[t.route_kind] ?? '#555', w = t.value_n && MAXV.route ? 2 + 6 * Math.sqrt(t.value_n / MAXV.route) : 3;
      tip(L.polyline(t.line.map(ll), {color:col, weight:w, opacity: t.state === 'disrupted' ? .5 : .85, dashArray:dash}).addTo(map), 'center');
      t.line.forEach(p => pts.push(p));
      if (!t.bidirectional) heads.push([t.line[t.line.length-2], t.line[t.line.length-1], col]);
      continue;
    }
    if (t.kind === 'region' && t.area) {
      const col = sideCol ?? REGION_COL[t.region_kind] ?? '#555', k = t.intensity ?? .5;
      for (const ring of rings(t.area)) { tip(L.polygon(ring.map(ll), {color:col, weight:1, opacity:.6, fillColor:col, fillOpacity:.08 + .5 * k, dashArray:dash}).addTo(map), 'center'); ring.forEach(p => pts.push(p)); }
      continue;
    }
    if (POINT_COL[t.kind] && t.at) {
      const col = t.state === 'infected' || t.state === 'peak' ? '#991b1b' : sideCol ?? POINT_COL[t.kind];
      const rad = t.value_n && MAXV[t.kind] ? 3 + 12 * Math.sqrt(t.value_n / MAXV[t.kind]) : 4;
      tip(L.circleMarker(ll(t.at), {radius:rad, color:'#111', weight:1, dashArray:dash, fillColor:col, fillOpacity: t.state === 'recovered' ? .3 : .8}).addTo(map), 'right');
      pts.push(t.at);
      continue;
    }
    const [col, wt] = TER[t.kind] ?? ['#555', 2];
    if (t.line) tip(L.polyline(t.line.map(ll), {color:col, weight:wt, opacity:.85, dashArray:dash}).addTo(map), 'center');
    if (t.area) for (const ring of rings(t.area)) tip(L.polygon(ring.map(ll), {color:col, weight:1, fillColor:col, fillOpacity:wt, dashArray:dash}).addTo(map), 'center');
    if (t.at) tip(L.circleMarker(ll(t.at), {radius:4, color:'#111', fillColor:'#fff', fillOpacity:1, weight:1.5}).addTo(map), 'right');
  }
  for (const mv of step.moves ?? []) {
    if (!Array.isArray(mv.path) || mv.path.length < 2) continue;
    const side = SIDE[mv.side ?? UNIT[mv.unit]?.side]; const col = side?.color ?? '#333';
    const path = mv.path.slice();
    if (mv.target && snap[mv.target]?.at) path[path.length-1] = snap[mv.target].at;
    L.polyline(path.map(ll), {color:col, weight: mv.type === 'charge' || mv.type === 'ram' ? 5 : 3, opacity: mv.conjectural ? .6 : .9, dashArray: MOVE_DASH[mv.type] ?? (mv.conjectural ? '7 5' : null)}).addTo(map);
    if (mv.continues?.toward) L.polyline([path[path.length-1], mv.continues.toward].map(ll), {color:col, weight:2, opacity:.45, dashArray:'4 6'}).addTo(map);
    heads.push([path[path.length-2], path[path.length-1], col]);
    path.forEach(p => pts.push(p));
  }
  for (const [uid, pl] of Object.entries(snap)) {
    const u = UNIT[uid]; if (!u || !pl.at) continue; const s = SIDE[u.side] ?? {color:'#374151'};
    if (pl.with && snap[pl.with]?.at) { const h = snap[pl.with]; pl.at = dest(h.at, (h.facing ?? 0) + 180, (h.depth ?? 60)/2 + 50); }
    const framed = pl.frame !== false;
    if (framed) pts.push(pl.at);
    const faded = FADED.includes(pl.state), dash = faded ? '4 4' : (pl.conjectural ? '6 4' : null);
    const tag = SMALL ? cut(pl.label ?? u.label, 16) : `${ABBR[u.kind] ?? u.kind} ${pl.label ?? u.label}${pl.state && pl.state !== 'ready' ? ' ('+pl.state+')' : ''}`;
    if (POINT_KINDS.includes(u.kind)) {
      L.circleMarker(ll(pl.at), {radius: u.kind === 'commander' ? 6 : 5, color:'#111', weight:1.5, dashArray:dash, fillColor:s.color, fillOpacity: faded ? .4 : 1}).addTo(map)
        .bindTooltip(tag, {permanent:true, className:'lbl', direction:'right', offset:[6,0]});
      continue;
    }
    const poly = formation(pl);
    if (framed) poly.forEach(p => pts.push(p));
    L.polygon(poly.map(ll), {color: faded ? '#555' : '#111', weight: pl.state === 'engaged' ? 2.5 : 1, dashArray: dash,
      fillColor: s.color, fillOpacity: pl.state === 'destroyed' ? .15 : faded ? .35 : pl.conjectural ? .55 : .8}).addTo(map);
    const front = dest(pl.at, pl.facing ?? 0, (pl.depth ?? 60)/2 + 10);
    L.polyline([pl.at, front].map(ll), {color:'#fff', weight:1.5, opacity:.9}).addTo(map);
    L.marker(ll(pl.at), {opacity:0}).addTo(map).bindTooltip(tag, {permanent:true, className:'lbl', direction:'center'});
  }
  for (const n of step.notes ?? []) {
    if (!n.at) continue;
    pts.push(n.at);
    L.circleMarker(ll(n.at), {radius:3, color:'#b45309', fillColor:'#b45309', fillOpacity:1}).addTo(map)
      .bindTooltip(cut(n.text, 26), {permanent:true, className:'note', direction:'top', offset:[0,-4]});
  }
  if (step.camera) map.setView(ll(step.camera.center), step.camera.zoom + ZOOM_SHIFT);
  else if (pts.length) map.fitBounds(L.latLngBounds(pts.map(ll)), {padding:[PAD,PAD], maxZoom:16});
  else map.setView([0,0], 2);
  // Arrowheads sized in screen pixels for the zoom the step is shown at.
  const c = map.getCenter(), mpp = 40075016.686 * Math.cos(c.lat*rad) / Math.pow(2, map.getZoom() + 8);
  for (const [a, b, col] of heads) {
    const h = brg(a, b), len = HEAD_PX * mpp;
    L.polygon([b, dest(b, h+150, len), dest(b, h-150, len)].map(ll), {color:col, weight:1, fillColor:col, fillOpacity:.95}).addTo(map);
  }
}
ORDER.forEach(draw);
</script></body></html>
"""


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("preview needs Chrome or Chromium on PATH")


def step_index(doc: dict, step: str | int | None) -> int | None:
    """A 0-based step index from a step id or a 1-based number."""
    if step is None:
        return None
    ids = [s.get("id") for s in doc.get("steps", [])]
    if str(step) in ids:
        return ids.index(str(step))
    if str(step).isdigit() and 1 <= int(step) <= len(ids):
        return int(step) - 1
    raise SystemExit(f"--step: no step '{step}' (ids: {', '.join(map(str, ids))})")


def render(doc: dict, step: int | None = None, mode: str | None = None) -> Path:
    """Render and return the PNG path. `step` is a 0-based index (mode 'step');
    otherwise `mode` is 'contact' (default) or 'all'."""
    mode = "step" if step is not None else (mode or "contact")
    width, height, cols, small = MODES[mode]
    flat = normalise(flatten_beats(doc))
    slug = flat.get("slug", "story")
    out_dir = OUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(flat.get("steps", []))
    if step is not None and not 0 <= step < n:
        raise SystemExit(f"--step must be 1..{n}")
    order = [step] if step is not None else list(range(n))
    if cols is None:
        cols = min(4, max(1, len(order)))
    rows = (len(order) + cols - 1) // cols
    gap = 6 if small else 10
    # Show the ground a step's camera would show in the atlas viewport, in this cell.
    zoom_shift = 1 + math.log2(width / VIEWPORT[0])
    html = (
        PAGE.replace("__DOC__", json.dumps(flat))
        .replace("__SNAPSHOTS__", json.dumps(resolve_steps(flat)))
        .replace("__FEATURES__", json.dumps(resolve_features(flat)))
        .replace("__ORDER__", json.dumps(order))
        .replace("__POINT_KINDS__", json.dumps(list(POINT_UNIT_KINDS) + ["standard", "ship"]))
        .replace("__ZOOM_SHIFT__", f"{zoom_shift:.3f}")
        .replace("__HEAD_PX__", "8" if small else "13")
        .replace("__PAD__", "10" if small else "24")
        .replace("__BODY__", "small" if small else "")
        .replace("__SMALL__", "true" if small else "false")
        .replace("__COLS__", str(cols))
        .replace("__GAP__", str(gap))
        .replace("__W__", str(width))
        .replace("__H__", str(height))
    )
    page = out_dir / "preview.html"
    page.write_text(html)
    png = out_dir / {"contact": "contact.png", "all": "grid.png", "step": f"step-{(step or 0) + 1:02d}.png"}[mode]
    cap_h = 20 if small else 26
    total_w = cols * (width + gap + 2) + gap
    total_h = rows * (height + cap_h + gap + 2) + gap + 26
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
