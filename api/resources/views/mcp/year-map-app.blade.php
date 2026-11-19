<x-mcp::app :title="$title">
    <x-slot:head>
@verbatim
<style>
:root{color-scheme:light dark;
 --t1:var(--color-text-primary,light-dark(#141413,#faf9f5));
 --t2:var(--color-text-secondary,light-dark(#3d3d3a,#c2c0b6));
 --t3:var(--color-text-tertiary,light-dark(#73726c,#9c9a92));
 --bg1:var(--color-background-primary,light-dark(#fff,#30302e));
 --bg2:var(--color-background-secondary,light-dark(#f5f4ed,#262624));
 --bd:var(--color-border-tertiary,light-dark(rgba(31,30,29,.15),rgba(222,220,209,.15)));
 --bd2:var(--color-border-secondary,light-dark(rgba(31,30,29,.3),rgba(222,220,209,.3)));
 --accent:var(--color-text-info,light-dark(#3266ad,#80aadd));
 --r:var(--border-radius-md,10px);
 --font:var(--font-sans,system-ui,-apple-system,"Segoe UI",sans-serif);
 --g-polity:light-dark(#b4543f,#d47a63);--g-place:light-dark(#6b7f4a,#9cae6f);--g-event:light-dark(#bd8a2c,#d9a94e);
 --g-economy:light-dark(#4d6a86,#7d9db8);--g-culture:light-dark(#8a5673,#bb87a3);}
*{box-sizing:border-box}
body{margin:0;padding:12px 14px;font:14px/1.45 var(--font);color:var(--t1);background:transparent;min-width:280px}
button{font:inherit;color:inherit;background:none;border:0;padding:0;margin:0;cursor:pointer;text-align:left}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.bar{display:flex;align-items:center;gap:4px;margin-bottom:8px}
.step{min-width:44px;height:44px;border-radius:var(--r);border:1px solid var(--bd2);text-align:center;font-size:13px;font-variant-numeric:tabular-nums;display:inline-flex;align-items:center;justify-content:center}
.year{flex:1;text-align:center;font-weight:600;font-size:17px;white-space:nowrap;font-variant-numeric:tabular-nums}
#stage{position:relative;height:300px;border-radius:var(--r);overflow:hidden;background:var(--bg2);border:1px solid var(--bd);transition:opacity .15s}
@media(min-width:520px){#stage{height:380px}}
#stage.busy{opacity:.55}
#map{position:absolute;inset:0}
.maplibregl-ctrl-attrib{font-size:10px}
.pin{width:34px;height:34px;display:flex;align-items:center;justify-content:center;border-radius:50%}
.pin i{width:14px;height:14px;border-radius:50%;background:var(--gc);border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35)}
.pin.sel i{width:20px;height:20px;box-shadow:0 0 0 2px var(--t1)}
svg.fb{display:block;width:100%;height:100%}
svg.fb text{font-family:var(--font);font-size:11px;fill:var(--t2);paint-order:stroke;stroke:var(--bg2);stroke-width:3px;stroke-linejoin:round}
svg.fb .grat{stroke:var(--bd);stroke-width:1}
svg.fb .gl{fill:var(--t3);stroke:none;font-size:10px}
svg.fb .pt{cursor:pointer}
svg.fb .pt:focus-visible{outline:none}
svg.fb .pt:focus-visible circle.d{stroke:var(--accent);stroke-width:3}
svg.fb circle.d{stroke:#fff;stroke-width:1.5}
svg.fb .sel circle.d{stroke:var(--t1);stroke-width:2.5}
.note{font-size:12px;color:var(--t3);margin-top:4px}
.legend{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:12px;color:var(--t2);margin:8px 0 0}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend i{width:10px;height:10px;border-radius:50%;background:var(--gc)}
.card{background:var(--bg2);border-radius:var(--r);padding:10px 12px;margin-top:8px}
.card h2{font-size:15px;margin:0}
.card .m{font-size:12px;color:var(--t3);margin:1px 0 4px}
.card p{margin:4px 0 8px;color:var(--t2);font-size:13px}
.row{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:var(--r);border:1px solid var(--bd2);font-weight:500}
.btn.primary{background:var(--t1);color:var(--color-text-inverse,light-dark(#fff,#141413));border-color:var(--t1)}
.foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;font-size:12px;color:var(--t3)}
.link{color:var(--accent);min-height:44px;display:inline-flex;align-items:center;font-size:13px;white-space:nowrap}
.empty{position:absolute;left:0;right:0;top:46%;text-align:center;color:var(--t2);font-size:13px;pointer-events:none}
.msg{color:var(--t2);padding:8px 0}
</style>
@endverbatim
        <script type="module">
@verbatim
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yr = (y) => (y == null ? '' : y < 0 ? `${-y} BC` : `AD ${y}`);
const GROUPS = { POLITY: ['Polities & society', 'polity'], PLACE: ['Places', 'place'], EVENT: ['Events', 'event'], ECONOMY: ['Economy', 'economy'], CULTURE: ['Culture', 'culture'] };
const gvar = (g) => (GROUPS[g] ? `var(--g-${GROUPS[g][1]})` : 'var(--t3)');
const MAPLIBRE = '5.21.0';
const CDN = `https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/${MAPLIBRE}/`;
const OFM = 'https://tiles.openfreemap.org/styles/';
const OHM_TILES = 'https://vtiles.openhistoricalmap.org/maps/ohm_admin/{z}/{x}/{y}.pbf';

// Year arithmetic without a year 0 (1 BC is -1, AD 1 is 1).
function addYears(y, d) {
  const a = (y < 0 ? y + 1 : y) + d;
  const r = a <= 0 ? a - 1 : a;
  return Math.max(-100000, Math.min(9999, r));
}
// OHM date filter for a year of ours (mirrors web/src/lib/ohm-layer-date-filter.ts: OHM years are astronomical).
function ohmYearFilter(year) {
  const oy = year < 0 ? year + 1 : year;
  const iso = (n) => (n < 0 ? '-' : '') + String(Math.abs(n)).padStart(4, '0') + '-01-01';
  const sIso = iso(oy), eIso = iso(oy + 1), sDec = oy, eDec = oy + 1;
  return ['all',
    ['any', ['has', 'start_date'], ['has', 'end_date']],
    ['any',
      ['all', ['has', 'start_decdate'], ['<', ['to-number', ['get', 'start_decdate']], eDec]],
      ['all', ['!', ['has', 'start_decdate']], ['has', 'start_date'], ['<', ['get', 'start_date'], eIso]],
      ['!', ['has', 'start_date']]],
    ['any',
      ['all', ['has', 'end_decdate'], ['>=', ['to-number', ['get', 'end_decdate']], sDec]],
      ['all', ['!', ['has', 'end_decdate']], ['has', 'end_date'], ['>=', ['get', 'end_date'], sIso]],
      ['!', ['has', 'end_date']]],
    ['<=', ['to-number', ['get', 'admin_level'], 99], 4],
  ];
}
const HIDE = /^(tunnel|road|bridge|building|aeroway|poi|highway|airport|boundary_|label_country|label_state|label_other|label_village|waterway_tunnel|park|landuse)/;
const TINTS = ['#c9a66b', '#8fae8b', '#a08fb8', '#c98b7e', '#7fa3b8'];

createMcpApp(async (app) => {
  const root = $('#root');
  const open = (url) => url && app.openLink(url).catch(() => {});
  const ask = (text) => app.sendMessage({ role: 'user', content: [{ type: 'text', text }] }).catch(() => {});
  app.autoResize();

  let args = {}, year = 0, shownYear = 0, entities = [], total = 0, capped = false, atlasUrl = '';
  let selected = null, mode = 'init', map = null, markers = [], busy = false, firstFit = true, errMsg = '';
  let theme = app.getHostContext()?.theme === 'dark' ? 'dark' : 'light';
  const pts = () => entities.filter((e) => e.lng != null && e.lat != null);

  root.innerHTML = `
    <div class="bar">
      <button type="button" class="step" data-d="-100" aria-label="100 years earlier">−100</button>
      <button type="button" class="step" data-d="-10" aria-label="10 years earlier">−10</button>
      <div class="year" id="year" aria-live="polite"></div>
      <button type="button" class="step" data-d="10" aria-label="10 years later">+10</button>
      <button type="button" class="step" data-d="100" aria-label="100 years later">+100</button>
    </div>
    <div id="stage"><div id="map"></div></div>
    <div class="note" id="note"></div>
    <div class="legend" id="legend"></div>
    <div id="card"></div>
    <div class="foot"><span id="count"></span><button type="button" class="link" id="atlas">Open in atlas</button></div>`;
  const stage = $('#stage');
  root.querySelectorAll('.step').forEach((b) => b.addEventListener('click', () => goto(addYears(year, Number(b.dataset.d)))));
  $('#atlas').addEventListener('click', () => open(atlasUrl));

  // ---------- shared UI ----------
  function drawChrome() {
    $('#year').textContent = yr(year);
    const n = pts().length;
    $('#count').textContent = errMsg || (n ? `${total}${capped ? '+' : ''} mapped · showing top ${n}` : 'Nothing mapped here for this year');
    const present = [...new Set(entities.map((e) => e.group))];
    $('#legend').innerHTML = present.map((g) => `<span><i style="--gc:${gvar(g)}"></i>${esc(GROUPS[g]?.[0] || 'Other')}</span>`).join('');
    drawCard();
  }
  function drawCard() {
    const e = entities.find((x) => x.id === selected);
    const el = $('#card');
    if (!e) { el.innerHTML = ''; return; }
    el.innerHTML = `<div class="card"><h2>${esc(e.name)}</h2>
      <div class="m">${esc([e.type_label, e.date_label, e.place].filter(Boolean).join(' · '))}</div>
      ${e.summary ? `<p>${esc(e.summary)}</p>` : ''}
      <div class="row"><button type="button" class="btn primary" data-open="${esc(e.atlas_url)}">Open in atlas</button>
      <button type="button" class="btn" data-ask="${esc(e.name)}">Tell me more</button></div></div>`;
    el.querySelector('[data-open]').addEventListener('click', (ev) => open(ev.currentTarget.dataset.open));
    el.querySelector('[data-ask]').addEventListener('click', (ev) => ask(`Tell me about ${ev.currentTarget.dataset.ask}`));
  }
  function select(id) {
    selected = selected === id ? null : id;
    drawCard();
    paintSelection();
  }
  function paintSelection() {
    markers.forEach((m) => m.el.classList.toggle('sel', m.id === selected));
    stage.querySelectorAll('svg.fb .pt').forEach((g) => g.classList.toggle('sel', g.dataset.id === selected));
  }

  // ---------- MapLibre ----------
  function mapSupported() {
    return new Promise((resolve) => {
      try {
        const c = document.createElement('canvas');
        if (!(c.getContext('webgl2') || c.getContext('webgl'))) return resolve(false);
        const u = URL.createObjectURL(new Blob(['postMessage(1)'], { type: 'text/javascript' }));
        const w = new Worker(u);
        const done = (ok) => { clearTimeout(t); w.terminate(); URL.revokeObjectURL(u); resolve(ok); };
        const t = setTimeout(() => done(false), 1500);
        w.onmessage = () => done(true);
        w.onerror = () => done(false);
      } catch (e) { resolve(false); }
    });
  }
  const loadScript = (src) => new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('script')); document.head.appendChild(s); });
  const loadCss = (href) => { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l); };

  function decorate() {
    // runs on every style load: strip modern detail, add OHM borders for `shownYear`
    const style = map.getStyle();
    (style.layers || []).forEach((l) => { if (HIDE.test(l.id)) map.setLayoutProperty(l.id, 'visibility', 'none'); });
    if (!map.getSource('ohm_admin')) {
      map.addSource('ohm_admin', { type: 'vector', tiles: [OHM_TILES], minzoom: 2, maxzoom: 14, attribution: '© <a href="https://www.openhistoricalmap.org/" target="_blank" rel="noopener">OpenHistoricalMap</a> contributors' });
    }
    const tint = ['match', ['%', ['abs', ['to-number', ['get', 'osm_id'], 0]], 5], 0, TINTS[0], 1, TINTS[1], 2, TINTS[2], 3, TINTS[3], TINTS[4]];
    const before = (style.layers || []).find((l) => l.type === 'symbol' && !HIDE.test(l.id))?.id;
    const f = ohmYearFilter(shownYear || year);
    if (!map.getLayer('ohm-fill')) map.addLayer({ id: 'ohm-fill', type: 'fill', source: 'ohm_admin', 'source-layer': 'boundaries', filter: f, paint: { 'fill-color': tint, 'fill-opacity': 0.3 } }, before);
    if (!map.getLayer('ohm-line')) map.addLayer({ id: 'ohm-line', type: 'line', source: 'ohm_admin', 'source-layer': 'boundaries', filter: f, paint: { 'line-color': theme === 'dark' ? '#e0c9a6' : '#7a5230', 'line-width': 1.1, 'line-opacity': 0.8 } }, before);
  }
  function applyOhmFilter() {
    if (!map || !map.getLayer('ohm-fill')) return;
    const f = ohmYearFilter(shownYear);
    map.setFilter('ohm-fill', f);
    map.setFilter('ohm-line', f);
  }
  function drawMarkers() {
    markers.forEach((m) => m.marker.remove());
    markers = pts().map((e) => {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'pin' + (e.id === selected ? ' sel' : '');
      el.style.setProperty('--gc', gvar(e.group));
      el.setAttribute('aria-label', e.name);
      el.innerHTML = '<i></i>';
      el.addEventListener('click', (ev) => { ev.stopPropagation(); select(e.id); });
      const marker = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([e.lng, e.lat]).addTo(map);
      return { id: e.id, el, marker };
    });
  }
  function fit() {
    const p = pts();
    if (!p.length) {
      const b = args.bbox;
      if (b) map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 20, duration: 0 });
      return;
    }
    if (p.length === 1) { map.jumpTo({ center: [p[0].lng, p[0].lat], zoom: 5 }); return; }
    const bounds = new maplibregl.LngLatBounds();
    p.forEach((e) => bounds.extend([e.lng, e.lat]));
    map.fitBounds(bounds, { padding: 44, maxZoom: 7, duration: 0 });
  }

  async function startMap() {
    const t0 = Date.now();
    let loaded = false, styleOk = false;
    const bail = (why) => { if (mode === 'svg') return; try { map?.remove(); } catch (e) { /* ignore */ } map = null; app.sendLog?.('info', `map fallback: ${why}`); startSvg(); };
    if (!(await mapSupported())) return bail('webgl or workers unavailable');
    try {
      loadCss(CDN + 'maplibre-gl.css');
      await Promise.race([loadScript(CDN + 'maplibre-gl.js'), new Promise((_, rej) => setTimeout(() => rej(new Error('script timeout')), 4000))]);
      if (!window.maplibregl) throw new Error('no maplibregl');
    } catch (e) { return bail(String(e.message || e)); }
    try {
      mode = 'map';
      map = new maplibregl.Map({ container: 'map', style: OFM + (theme === 'dark' ? 'fiord' : 'liberty'), center: [10, 40], zoom: 2, attributionControl: { compact: true }, cooperativeGestures: true, fadeDuration: 0 });
    } catch (e) { return bail(String(e.message || e)); }
    map.on('style.load', () => { styleOk = true; try { decorate(); } catch (e) { /* ignore */ } });
    map.on('error', () => { if (!styleOk) bail('style failed'); });
    map.once('load', () => {
      loaded = true;
      document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
      document.querySelector('.maplibregl-ctrl-attrib')?.removeAttribute('open');
      drawMarkers();
      if (firstFit) { fit(); firstFit = false; }
    });
    const check = (limit) => setTimeout(() => {
      if (loaded || mode !== 'map') return;
      if (styleOk && limit < 9000) return check(9000);
      bail(`map not loaded after ${Date.now() - t0} ms`);
    }, limit - (Date.now() - t0));
    check(4000);
  }

  // ---------- SVG fallback ----------
  function startSvg() {
    mode = 'svg';
    $('#note').textContent = 'Simplified map: the interactive map is not available here.';
    drawSvg();
  }
  function drawSvg() {
    const W = Math.max(280, stage.clientWidth), H = stage.clientHeight || 300;
    const p = pts();
    if (!p.length) { stage.innerHTML = '<div class="empty">Nothing mapped here for this year.</div>'; return; }
    let a = Math.min(...p.map((e) => e.lng)), b = Math.max(...p.map((e) => e.lng));
    let c = Math.min(...p.map((e) => e.lat)), d = Math.max(...p.map((e) => e.lat));
    const midLng = (a + b) / 2, midLat = (c + d) / 2, k = Math.max(0.2, Math.cos((midLat * Math.PI) / 180));
    const spanLng = Math.max(b - a, 4), spanLat = Math.max(d - c, 4);
    const pad = 34;
    const s = Math.min((W - 2 * pad) / (spanLng * k), (H - 2 * pad) / spanLat);
    const X = (lng) => W / 2 + (lng - midLng) * k * s, Y = (lat) => H / 2 - (lat - midLat) * s;
    // graticule
    const steps = [1, 2, 5, 10, 15, 30, 45];
    const gs = steps.find((st) => (W / (st * k * s)) <= 8) || 45;
    let g = '';
    for (let lng = Math.max(-180, Math.ceil((midLng - W / (2 * k * s)) / gs) * gs); lng <= Math.min(180, midLng + W / (2 * k * s)); lng += gs) {
      g += `<line class="grat" x1="${X(lng)}" y1="0" x2="${X(lng)}" y2="${H}"/><text class="gl" x="${X(lng) + 3}" y="${H - 4}">${Math.abs(lng)}°${lng < 0 ? 'W' : lng > 0 ? 'E' : ''}</text>`;
    }
    for (let lat = Math.max(-90, Math.ceil((midLat - H / (2 * s)) / gs) * gs); lat <= Math.min(90, midLat + H / (2 * s)); lat += gs) {
      g += `<line class="grat" x1="0" y1="${Y(lat)}" x2="${W}" y2="${Y(lat)}"/><text class="gl" x="4" y="${Y(lat) - 3}">${Math.abs(lat)}°${lat < 0 ? 'S' : lat > 0 ? 'N' : ''}</text>`;
    }
    // labels for the top few (entities are ranked by impact), skipping collisions
    const taken = [];
    const labels = new Map();
    const hit = (r) => taken.some((t) => r[0] < t[2] && r[2] > t[0] && r[1] < t[3] && r[3] > t[1]);
    p.slice(0, 8).forEach((e) => {
      const txt = e.name.length > 22 ? e.name.slice(0, 21) + '…' : e.name, w = txt.length * 5.9 + 4;
      const x = X(e.lng), y = Y(e.lat);
      for (const side of [1, -1]) {
        const r = side === 1 ? [x + 9, y - 7, x + 9 + w, y + 7] : [x - 9 - w, y - 7, x - 9, y + 7];
        if (r[0] >= 2 && r[2] <= W - 2 && !hit(r)) { taken.push(r); labels.set(e.id, [txt, side === 1 ? x + 9 : x - 9, y + 4, side === 1 ? 'start' : 'end']); break; }
      }
    });
    stage.innerHTML = `<svg class="fb" viewBox="0 0 ${W} ${H}" role="group" aria-label="Map of ${p.length} entities in ${esc(yr(year))}">${g}${p.map((e) => {
      const l = labels.get(e.id);
      return `<g class="pt ${e.id === selected ? 'sel' : ''}" data-id="${esc(e.id)}" tabindex="0" role="button" aria-label="${esc(e.name)}"><title>${esc(e.name)}</title>
        <circle r="18" cx="${X(e.lng)}" cy="${Y(e.lat)}" fill="transparent"/><circle class="d" r="6" cx="${X(e.lng)}" cy="${Y(e.lat)}" fill="${gvar(e.group)}"/>
        ${l ? `<text x="${l[1]}" y="${l[2]}" text-anchor="${l[3]}">${esc(l[0])}</text>` : ''}</g>`;
    }).join('')}</svg>`;
    stage.querySelectorAll('.pt').forEach((el) => {
      el.addEventListener('click', () => select(el.dataset.id));
      el.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(el.dataset.id); } });
    });
  }

  // ---------- data ----------
  function applyResult(sc) {
    entities = sc.entities || [];
    total = sc.total ?? entities.length;
    capped = !!sc.total_capped;
    atlasUrl = sc.atlas_url || atlasUrl;
    shownYear = sc.year ?? shownYear;
    args = { bbox: sc.bbox || undefined, region: sc.region || undefined, types: sc.types || undefined };
    if (selected && !entities.some((e) => e.id === selected)) selected = null;
    errMsg = '';
    drawChrome();
    if (mode === 'map' && map) {
      applyOhmFilter();
      if (!firstFit) drawMarkers();
    } else if (mode === 'svg') drawSvg();
  }
  async function goto(y) {
    year = y;
    $('#year').textContent = yr(year);
    if (busy) return;
    busy = true;
    stage.classList.add('busy');
    try {
      for (;;) {
        const target = year;
        const arg = { year: target };
        if (args.bbox) arg.bbox = args.bbox;
        if (args.region) arg.region = args.region;
        if (args.types) arg.types = args.types;
        const r = await app.callServerTool({ name: 'what-was-happening', arguments: arg });
        if (r.isError || !r.structuredContent) { errMsg = r.content?.[0]?.text || 'Could not load that year.'; drawChrome(); break; }
        if (target === year) { applyResult(r.structuredContent); if (mode === 'map' && map?.loaded()) { /* keep camera */ } break; }
      }
    } catch (e) { errMsg = 'Could not load that year.'; drawChrome(); }
    busy = false;
    stage.classList.remove('busy');
  }

  let started = false;
  app.onToolResult((result) => {
    const sc = result?.structuredContent;
    if (!sc?.entities) {
      root.innerHTML = `<p class="msg">${esc(result?.content?.find((c) => c.type === 'text')?.text || 'No map to show.')}</p>`;
      return;
    }
    year = sc.year;
    applyResult(sc);
    if (!started) { started = true; startMap(); }
  });

  app.onHostContextChanged((ctx) => {
    const t = ctx?.theme === 'dark' ? 'dark' : 'light';
    if (t === theme) return;
    theme = t;
    if (mode === 'map' && map) {
      try { map.getLayer('ohm-fill') && map.removeLayer('ohm-fill'); map.getLayer('ohm-line') && map.removeLayer('ohm-line'); map.getSource('ohm_admin') && map.removeSource('ohm_admin'); map.setStyle(OFM + (theme === 'dark' ? 'fiord' : 'liberty')); } catch (e) { /* ignore */ }
    }
  });
});
@endverbatim
        </script>
    </x-slot:head>

    <div id="root"><p class="msg">Loading map…</p></div>
</x-mcp::app>
