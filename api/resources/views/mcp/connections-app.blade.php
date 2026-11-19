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
h1{font-size:18px;line-height:1.2;margin:0;font-weight:600}
.sub{color:var(--t2);font-size:13px;margin-top:2px}
svg{display:block;width:100%;overflow:visible}
svg text{font-family:var(--font);font-size:11px;fill:var(--t2);paint-order:stroke;stroke:var(--bg1);stroke-width:3px;stroke-linejoin:round}
svg .sel text,svg text.c{fill:var(--t1);font-weight:600}
.edge{stroke:var(--bd2);stroke-width:1.2;fill:none}
.edge.cross{stroke-dasharray:3 3;opacity:.7}
.edge.hot{stroke:var(--t2);stroke-width:2}
.hit{stroke:transparent;stroke-width:14;fill:none;cursor:pointer}
.node{cursor:pointer}
.node:focus-visible{outline:none}
.node:focus-visible .shape{stroke:var(--accent);stroke-width:3}
.shape{stroke:var(--bg1);stroke-width:1.5}
.sel .shape{stroke:var(--t1);stroke-width:2.5}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--t2);margin:6px 0 4px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.detail{background:var(--bg2);border-radius:var(--r);padding:10px 12px;margin:8px 0}
.detail h2{font-size:15px;margin:0}
.detail .m{font-size:12px;color:var(--t3);margin:1px 0 4px}
.detail p{margin:4px 0;color:var(--t2);font-size:13px}
.detail ul{margin:4px 0;padding-left:18px;color:var(--t2);font-size:13px}
.row{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:var(--r);border:1px solid var(--bd2);font-weight:500}
.btn.primary{background:var(--t1);color:var(--color-text-inverse,light-dark(#fff,#141413));border-color:var(--t1)}
h3{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--t3);margin:12px 0 2px}
.list{list-style:none;margin:0;padding:0}
.li{display:block;width:100%;min-height:44px;padding:6px 0;border-top:1px solid var(--bd);font-size:13px;color:var(--t2)}
.list li:first-child .li{border-top:0}
.li b{color:var(--t1);font-weight:500}
.li small{color:var(--t3);margin-left:6px}
.more{color:var(--accent);min-height:44px;display:inline-flex;align-items:center;font-size:13px}
.hint{font-size:12px;color:var(--t3)}
.msg{color:var(--t2);padding:8px 0}
</style>
@endverbatim
        <script type="module">
@verbatim
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yr = (y) => (y == null ? '' : y < 0 ? `${-y} BC` : String(y));
const span = (s, e) => (s == null && e == null ? '' : s === e || e == null ? yr(s) : s == null ? `until ${yr(e)}` : `${yr(s)}–${yr(e)}`);
const GROUPS = {
  POLITY: ['Polities & society', 'var(--g-polity)', 'circle'],
  PLACE: ['Places', 'var(--g-place)', 'square'],
  EVENT: ['Events', 'var(--g-event)', 'diamond'],
  ECONOMY: ['Economy', 'var(--g-economy)', 'triangle'],
  CULTURE: ['Culture', 'var(--g-culture)', 'hex'],
};
const gInfo = (g) => GROUPS[g] || ['Other', 'var(--t3)', 'circle'];
// A marker shape centred on (0,0), size r.
function shape(kind, r, fill, extra = '') {
  const f = `class="shape" fill="${fill}" ${extra}`;
  switch (kind) {
    case 'square': return `<rect ${f} x="${-r * .85}" y="${-r * .85}" width="${r * 1.7}" height="${r * 1.7}" rx="2"/>`;
    case 'diamond': return `<path ${f} d="M0 ${-r * 1.2}L${r * 1.2} 0L0 ${r * 1.2}L${-r * 1.2} 0Z"/>`;
    case 'triangle': return `<path ${f} d="M0 ${-r * 1.15}L${r * 1.15} ${r * .85}L${-r * 1.15} ${r * .85}Z"/>`;
    case 'hex': return `<path ${f} d="M${r} 0L${r / 2} ${r * .87}L${-r / 2} ${r * .87}L${-r} 0L${-r / 2} ${-r * .87}L${r / 2} ${-r * .87}Z"/>`;
    default: return `<circle ${f} r="${r}"/>`;
  }
}
const short = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

createMcpApp(async (app) => {
  const root = $('#root');
  const open = (url) => url && app.openLink(url).catch(() => {});
  const ask = (text) => app.sendMessage({ role: 'user', content: [{ type: 'text', text }] }).catch(() => {});
  app.autoResize();
  let data = null, selected = null, hotEdge = null, listAll = false;

  function draw() {
    const { center, nodes, edges } = data;
    const byId = new Map([[center.id, center], ...nodes.map((n) => [n.id, n])]);
    const W = Math.max(280, document.documentElement.clientWidth - 28);
    const narrow = W < 520;
    const withLabels = !narrow || nodes.length <= 6;
    const nameRoom = withLabels ? (narrow ? 78 : 110) : 22;
    const cx = W / 2;
    const R = Math.max(60, Math.min(cx - nameRoom, narrow ? 170 : 200));
    const H = Math.round(2 * R + 56);
    const cy = H / 2;
    const pos = new Map([[center.id, [cx, cy]]]);
    nodes.forEach((n, i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, nodes.length);
      pos.set(n.id, [cx + R * Math.cos(a), cy + R * Math.sin(a), a]);
    });
    const NR = 8, CR = 13;
    const labelled = new Set(withLabels ? nodes.slice(0, narrow ? 6 : 16).map((n) => n.id) : []);
    const touches = (e, id) => e.source === id || e.target === id;

    const edgeSvg = edges.filter((e) => pos.has(e.source) && pos.has(e.target)).map((e, i) => {
      const [x1, y1] = pos.get(e.source), [x2, y2] = pos.get(e.target);
      const d = Math.hypot(x2 - x1, y2 - y1) || 1;
      const rs = e.source === center.id ? CR : NR, rt = e.target === center.id ? CR : NR;
      const ax = x1 + ((x2 - x1) / d) * (rs + 1), ay = y1 + ((y2 - y1) / d) * (rs + 1);
      const bx = x2 - ((x2 - x1) / d) * (rt + 4), by = y2 - ((y2 - y1) / d) * (rt + 4);
      const cross = e.source !== center.id && e.target !== center.id;
      const hot = hotEdge === i || (selected && touches(e, selected));
      // arrow head at target
      const ux = (bx - ax) / (Math.hypot(bx - ax, by - ay) || 1), uy = (by - ay) / (Math.hypot(bx - ax, by - ay) || 1);
      const head = `M${bx} ${by}L${bx - ux * 6 - uy * 3.5} ${by - uy * 6 + ux * 3.5}L${bx - ux * 6 + uy * 3.5} ${by - uy * 6 - ux * 3.5}Z`;
      return `<g data-e="${i}"><title>${esc(byId.get(e.source)?.name)} ${esc(e.label)} ${esc(byId.get(e.target)?.name)}</title>
        <line class="edge ${cross ? 'cross' : ''} ${hot ? 'hot' : ''}" x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}"/>
        <path d="${head}" fill="${hot ? 'var(--t2)' : 'var(--bd2)'}"/>
        <line class="hit" x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}"/></g>`;
    }).join('');

    const edgeLabel = (() => {
      const e = hotEdge != null ? edges[hotEdge] : null;
      if (!e || !pos.has(e.source) || !pos.has(e.target)) return '';
      const [x1, y1] = pos.get(e.source), [x2, y2] = pos.get(e.target);
      return `<text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 5}" text-anchor="middle" class="c">${esc(e.label)}</text>`;
    })();

    const nodeSvg = nodes.map((n) => {
      const [x, y, a] = pos.get(n.id);
      const [, col, kind] = gInfo(n.group);
      const right = Math.cos(a) >= -0.15;
      const lab = labelled.has(n.id)
        ? `<text x="${right ? NR + 5 : -NR - 5}" y="4" text-anchor="${right ? 'start' : 'end'}">${esc(short(n.name, W < 520 ? 14 : 22))}</text>` : '';
      return `<g class="node ${selected === n.id ? 'sel' : ''}" data-n="${esc(n.id)}" transform="translate(${x} ${y})" tabindex="0" role="button" aria-label="${esc(n.name)}, ${esc(n.type_label)}">
        <circle r="20" fill="transparent"/>${shape(kind, NR, col)}${lab}</g>`;
    }).join('');
    const [, ccol, ckind] = gInfo(center.group);
    const centerSvg = `<g class="node ${selected === center.id ? 'sel' : ''}" data-n="${esc(center.id)}" transform="translate(${cx} ${cy})" tabindex="0" role="button" aria-label="${esc(center.name)}">
      <circle r="24" fill="transparent"/>${shape(ckind, CR, ccol)}<text class="c" y="${CR + 15}" text-anchor="middle">${esc(short(center.name, W < 520 ? 20 : 30))}</text></g>`;

    const present = [...new Set([center, ...nodes].map((n) => n.group))];
    const legend = present.map((g) => { const [l, c, k] = gInfo(g); return `<span><svg width="14" height="14" viewBox="-9 -9 18 18" style="width:14px">${shape(k, 6, c)}</svg>${esc(l)}</span>`; }).join('');

    // detail
    let detail = '';
    const sel = selected && byId.get(selected);
    if (sel) {
      const rel = edges.filter((e) => touches(e, sel.id)).map((e) => {
        const other = byId.get(e.source === sel.id ? e.target : e.source);
        const text = e.source === sel.id ? `${e.label} ${other?.name}` : `${other?.name} ${e.label} ${sel.name}`;
        return `<li>${esc(text)} ${span(e.start_year, e.end_year) ? `<small>(${esc(span(e.start_year, e.end_year))})</small>` : ''}</li>`;
      }).join('');
      detail = `<div class="detail"><h2>${esc(sel.name)}</h2>
        <div class="m">${esc([sel.type_label, sel.date_label, sel.place].filter(Boolean).join(' · '))}</div>
        ${sel.summary ? `<p>${esc(sel.summary)}</p>` : ''}${rel ? `<ul>${rel}</ul>` : ''}
        <div class="row"><button type="button" class="btn primary" data-open="${esc(sel.atlas_url)}">Open in atlas</button>
        ${sel.id !== center.id ? `<button type="button" class="btn" data-ask="${esc(sel.name)}">Tell me more</button>` : ''}</div></div>`;
    }

    const rows = edges.filter((e) => byId.has(e.source) && byId.has(e.target));
    const SHOW = 6;
    const list = rows.slice(0, listAll ? rows.length : SHOW).map((e) => {
      const s = byId.get(e.source), t = byId.get(e.target);
      const other = s.id === center.id ? t : s;
      return `<li><button type="button" class="li" data-n="${esc(other.id)}"><b>${esc(s.name)}</b> ${esc(e.label)} <b>${esc(t.name)}</b>${span(e.start_year, e.end_year) ? `<small>${esc(span(e.start_year, e.end_year))}</small>` : ''}</button></li>`;
    }).join('');

    root.innerHTML = `
      <h1>${esc(center.name)}</h1>
      <div class="sub">${nodes.length} connected ${nodes.length === 1 ? 'entity' : 'entities'}${center.date_label ? ` · ${esc(center.date_label)}` : ''}</div>
      ${nodes.length ? `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="Graph of ${esc(center.name)} and its connections">${edgeSvg}${nodeSvg}${centerSvg}${edgeLabel}</svg>
      <div class="legend">${legend}</div><div class="hint">Tap a node for details, a line for its relationship.</div>` : '<p class="msg">No connections found.</p>'}
      ${detail}
      ${rows.length ? `<h3>All connections</h3><ul class="list">${list}</ul>${rows.length > SHOW ? `<button type="button" class="more" id="all">${listAll ? 'Show fewer' : `Show all ${rows.length}`}</button>` : ''}` : ''}
      ${sel ? '' : `<div class="row" style="margin-top:8px"><button type="button" class="btn primary" data-open="${esc(center.atlas_url)}">Open in atlas</button></div>`}`;

    root.querySelectorAll('[data-n]').forEach((el) => {
      const pick = () => { selected = selected === el.dataset.n ? null : el.dataset.n; hotEdge = null; draw(); };
      el.addEventListener('click', pick);
      el.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); pick(); } });
    });
    root.querySelectorAll('g[data-e]').forEach((el) => {
      const i = Number(el.dataset.e);
      const show = () => { if (hotEdge !== i) { hotEdge = i; draw(); } };
      el.addEventListener('mouseenter', show);
      el.addEventListener('click', show);
      el.addEventListener('mouseleave', () => { if (hotEdge === i) { hotEdge = null; draw(); } });
    });
    root.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => open(b.dataset.open)));
    root.querySelectorAll('[data-ask]').forEach((b) => b.addEventListener('click', () => ask(`Tell me about ${b.dataset.ask}`)));
    $('#all')?.addEventListener('click', () => { listAll = !listAll; draw(); });
  }

  app.onToolResult((result) => {
    const sc = result?.structuredContent;
    if (!sc?.center) {
      root.innerHTML = `<p class="msg">${esc(result?.content?.find((c) => c.type === 'text')?.text || 'No connections to show.')}</p>`;
      return;
    }
    data = { center: sc.center, nodes: sc.nodes || [], edges: sc.edges || [] };
    selected = null; hotEdge = null; listAll = false;
    draw();
  });

  let lastW = 0;
  new ResizeObserver(() => {
    const w = document.documentElement.clientWidth;
    if (data && lastW && Math.abs(w - lastW) > 8) draw();
    lastW = w;
  }).observe(document.documentElement);
});
@endverbatim
        </script>
    </x-slot:head>

    <div id="root"><p class="msg">Loading connections…</p></div>
</x-mcp::app>
