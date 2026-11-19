<x-mcp::app :title="$title">
    <x-slot:head>
@verbatim
<style>
:root{color-scheme:light dark;
 --t1:var(--color-text-primary,light-dark(#141413,#faf9f5));
 --t2:var(--color-text-secondary,light-dark(#3d3d3a,#c2c0b6));
 --t3:var(--color-text-tertiary,light-dark(#73726c,#9c9a92));
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
h1{font-size:20px;line-height:1.2;margin:0 0 4px;font-weight:600}
.top{display:grid;gap:12px}
@media(min-width:520px){.top.has-img{grid-template-columns:190px 1fr}}
figure{margin:0}
.img{display:block;width:100%;max-height:200px;object-fit:cover;object-position:50% 15%;border-radius:var(--r);background:var(--bg2)}
@media(min-width:520px){.img{height:190px;max-height:none}figure{align-self:start}}
.credit{font-size:12px;color:var(--t3);margin-top:4px;line-height:1.35}
.credit button{color:var(--t3);text-decoration:underline;display:inline;min-height:0}
.meta{display:flex;flex-wrap:wrap;gap:2px 10px;color:var(--t2);font-size:13px;align-items:center}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;background:var(--gc,var(--t3))}
.warn{display:inline-block;margin-top:6px;font-size:12px;color:var(--color-text-warning,light-dark(#5a4815,#d1a041));background:var(--color-background-warning,light-dark(#f6eedf,#483a0f));border-radius:6px;padding:1px 8px}
.txt{margin-top:8px;color:var(--t2)}
.txt p{margin:0 0 6px}.txt p:last-child{margin:0}
.txt.clamp{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.more{color:var(--accent);min-height:44px;display:inline-flex;align-items:center;font-size:13px}
h2{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--t3);margin:14px 0 2px}
.rels{list-style:none;margin:0;padding:0}
.rel{display:grid;grid-template-columns:1fr auto;gap:0 10px;align-items:center;width:100%;min-height:44px;padding:6px 0;border-top:1px solid var(--bd)}
.rels li:first-child .rel{border-top:0}
.rl{grid-column:1;font-size:12px;color:var(--t3)}
.rn{grid-column:1;font-weight:500;overflow-wrap:anywhere}
.rd{grid-column:2;grid-row:1/3;font-size:12px;color:var(--t3);white-space:nowrap}
.rel:hover .rn{text-decoration:underline}
.actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:var(--r);border:1px solid var(--bd2);font-weight:500;text-align:center}
.btn.primary{background:var(--t1);color:var(--color-text-inverse,light-dark(#fff,#141413));border-color:var(--t1)}
.msg{color:var(--t2);padding:8px 0}
.skel{height:80px;border-radius:var(--r);background:var(--bg2)}
</style>
@endverbatim
        <script type="module">
@verbatim
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const GROUP = { POLITY: 'polity', PLACE: 'place', EVENT: 'event', ECONOMY: 'economy', CULTURE: 'culture' };
const yr = (y) => (y == null ? '' : y < 0 ? `${-y} BC` : String(y));
const span = (s, e) => (s == null && e == null ? '' : s === e || e == null ? yr(s) : s == null ? `until ${yr(e)}` : `${yr(s)}–${yr(e)}`);

createMcpApp(async (app) => {
  const root = $('#root');
  const open = (url) => url && app.openLink(url).catch(() => {});
  const ask = (text) => app.sendMessage({ role: 'user', content: [{ type: 'text', text }] }).catch(() => {});
  app.autoResize();

  function render(result) {
    const e = result?.structuredContent?.entity;
    if (!e) {
      const t = result?.content?.find((c) => c.type === 'text')?.text;
      root.innerHTML = `<p class="msg">${esc(t || 'No entity to show.')}</p>`;
      return;
    }
    const img = e.image;
    const body = (e.description && e.description.length > (e.summary || '').length ? e.description : e.summary) || '';
    const paras = body.split(/\n+/).filter(Boolean).map((p) => `<p>${esc(p)}</p>`).join('');
    const rels = e.relationships || [];
    const SHOW = 5;
    const gc = GROUP[e.group] ? `var(--g-${GROUP[e.group]})` : 'var(--t3)';
    const unreviewed = ['pipeline_draft', 'needs_review'].includes(e.verification_status);
    const credit = img && [img.credit, img.license].filter(Boolean).join(' · ');
    root.innerHTML = `
      <div class="top ${img ? 'has-img' : ''}">
        ${img ? `<figure>
          <img class="img" src="${esc(img.thumb_url)}" alt="${esc(e.name)}" referrerpolicy="no-referrer">
          <figcaption class="credit">${esc(credit)}${credit ? ' · ' : ''}<button type="button" data-open="${esc(img.source_url || '')}">Wikimedia Commons</button></figcaption>
        </figure>` : ''}
        <div>
          <h1>${esc(e.name)}</h1>
          <div class="meta">
            <span><i class="dot" style="--gc:${gc}"></i>${esc(e.type_label)}</span>
            ${e.date_label ? `<span>${esc(e.date_label)}</span>` : ''}
            ${e.place ? `<span>${esc(e.place)}</span>` : ''}
          </div>
          ${unreviewed ? '<span class="warn">Unreviewed record</span>' : ''}
          ${paras ? `<div class="txt clamp" id="txt">${paras}</div><button type="button" class="more" id="more" hidden>More</button>` : ''}
        </div>
      </div>
      ${rels.length ? `<h2>Relationships</h2><ul class="rels" id="rels"></ul>${rels.length > SHOW ? `<button type="button" class="more" id="relmore">Show all ${rels.length}</button>` : ''}` : ''}
      <div class="actions"><button type="button" class="btn primary" data-open="${esc(e.atlas_url)}">Open in atlas</button></div>`;

    const image = $('.img');
    if (image) {
      image.addEventListener('error', () => { $('figure').remove(); $('.top').classList.remove('has-img'); });
    }
    root.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => open(b.dataset.open)));

    const txt = $('#txt'), more = $('#more');
    if (txt && more) {
      requestAnimationFrame(() => {
        if (txt.scrollHeight > txt.clientHeight + 2) more.hidden = false;
      });
      more.addEventListener('click', () => {
        const clamped = txt.classList.toggle('clamp');
        more.textContent = clamped ? 'More' : 'Less';
      });
    }

    const list = $('#rels');
    if (list) {
      let all = false;
      const draw = () => {
        list.innerHTML = (all ? rels : rels.slice(0, SHOW)).map((r, i) => `
          <li><button type="button" class="rel" data-i="${i}" title="Ask Claude about ${esc(r.other.name)}">
            <span class="rl">${esc(r.label)}</span>
            <span class="rn">${esc(r.other.name)}</span>
            <span class="rd">${esc(span(r.start_year, r.end_year))}</span>
          </button></li>`).join('');
        list.querySelectorAll('.rel').forEach((b) => b.addEventListener('click', () => ask(`Tell me about ${rels[b.dataset.i].other.name}`)));
      };
      draw();
      const rm = $('#relmore');
      rm?.addEventListener('click', () => { all = !all; rm.textContent = all ? 'Show fewer' : `Show all ${rels.length}`; draw(); });
    }
  }

  app.onToolResult(render);
});
@endverbatim
        </script>
    </x-slot:head>

    <div id="root"><div class="skel" style="height:80px;border-radius:10px"></div></div>
</x-mcp::app>
