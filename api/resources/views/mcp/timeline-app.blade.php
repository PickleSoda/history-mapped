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
 --font:var(--font-sans,system-ui,-apple-system,"Segoe UI",sans-serif);}
*{box-sizing:border-box}
body{margin:0;padding:12px 14px;font:14px/1.45 var(--font);color:var(--t1);background:transparent;min-width:280px}
button{font:inherit;color:inherit;background:none;border:0;padding:0;margin:0;cursor:pointer;text-align:left}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h1{font-size:20px;line-height:1.2;margin:0 0 4px;font-weight:600}
.sub{color:var(--t2);font-size:13px}
.sum{color:var(--t2);margin:6px 0 0}
.link{color:var(--accent);min-height:44px;display:flex;align-items:center;font-size:13px;margin:-12px 0}
.link[hidden]{display:none}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;border-radius:var(--r);border:1px solid var(--bd2);font-weight:500}
.btn.primary{background:var(--t1);color:var(--color-text-inverse,light-dark(#fff,#141413));border-color:var(--t1)}
.btn[disabled]{opacity:.35;cursor:default}
.date{font-size:12px;font-weight:600;color:var(--t2);font-variant-numeric:tabular-nums}
.et{font-weight:600;margin:2px 0 4px;line-height:1.3;overflow-wrap:anywhere}
.tx{color:var(--t2);font-size:13px;overflow-wrap:anywhere}
.tx.clamp{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.ent{font-size:12px;color:var(--accent);min-height:44px;display:flex;align-items:center;margin:-12px 0 -8px}
/* horizontal */
.h{margin-top:12px}
.strip{display:flex;gap:2px;height:14px;align-items:center;margin-bottom:10px}
.strip i{flex:1;height:6px;border-radius:2px;background:var(--bd2)}
.strip i.on{background:var(--accent);height:10px}
.cols{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:0 12px;position:relative;padding-top:14px}
.cols:before{content:"";position:absolute;left:0;right:0;top:6px;height:2px;background:var(--bd2)}
.col{position:relative;min-width:0}
.col:before{content:"";position:absolute;top:-12px;left:0;width:10px;height:10px;border-radius:50%;background:var(--accent);border:2px solid var(--color-background-primary,light-dark(#fff,#30302e))}
.pager{display:flex;align-items:center;gap:8px;margin-top:8px}
.pager .pos{flex:1;text-align:center;font-size:12px;color:var(--t3)}
/* vertical */
.v{margin-top:10px;position:relative;padding-left:20px}
.v:before{content:"";position:absolute;left:4px;top:8px;bottom:8px;width:2px;background:var(--bd2)}
.vi{position:relative;padding:0 0 14px}
.vi:before{content:"";position:absolute;left:-20px;top:3px;width:10px;height:10px;border-radius:50%;background:var(--accent);border:2px solid var(--color-background-primary,light-dark(#fff,#30302e))}
.actions{margin-top:6px}
.msg{color:var(--t2);padding:8px 0}
</style>
@endverbatim
        <script type="module">
@verbatim
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yr = (y) => (y == null ? '' : y < 0 ? `${-y} BC` : String(y));
const span = (s, e) => (s == null && e == null ? '' : s === e || e == null ? yr(s) : s == null ? `until ${yr(e)}` : `${yr(s)}–${yr(e)}`);

createMcpApp(async (app) => {
  const root = $('#root');
  const open = (url) => url && app.openLink(url).catch(() => {});
  app.autoResize();
  let data = null, page = 0, shown = 5;
  const expanded = new Set();

  const body = (en) => {
    const core = en.title.replace(/\u2026$/, '');
    const rest = en.title.endsWith('\u2026') ? '' : en.text.startsWith(core) ? en.text.slice(core.length).trim() : '';
    return rest || en.text;
  };
  const entry = (en, idx) => `
    <div class="date">${esc(en.date_label || span(en.start_year, en.end_year) || `Step ${en.sequence}`)}</div>
    <div class="et">${esc(en.title)}</div>
    <div class="tx ${expanded.has(idx) ? '' : 'clamp'}" data-tx="${idx}">${esc(body(en))}</div>
    <button type="button" class="link" data-more="${idx}" hidden></button>
    ${en.entity ? `<button type="button" class="ent" data-open="${esc(en.entity.atlas_url)}">${esc(en.entity.name)} ↗</button>` : ''}`;

  function wire(scope) {
    scope.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => open(b.dataset.open)));
    scope.querySelectorAll('[data-more]').forEach((b) => {
      const idx = Number(b.dataset.more);
      const tx = scope.querySelector(`[data-tx="${idx}"]`);
      const label = () => { b.textContent = expanded.has(idx) ? 'Less' : 'More'; };
      requestAnimationFrame(() => {
        if (expanded.has(idx) || tx.scrollHeight > tx.clientHeight + 2) { b.hidden = false; label(); }
      });
      b.addEventListener('click', () => {
        expanded.has(idx) ? expanded.delete(idx) : expanded.add(idx);
        tx.classList.toggle('clamp', !expanded.has(idx));
        label();
      });
    });
  }

  function draw() {
    if (!data) return;
    const { chronicle: c, entries } = data;
    const w = document.documentElement.clientWidth;
    const wide = w >= 520;
    const dates = span(c.start_year, c.end_year);
    let body = '';
    if (!entries.length) {
      body = '<p class="msg">This chronicle has no entries yet.</p>';
    } else if (wide) {
      const n = Math.max(2, Math.min(5, Math.floor((w - 28) / 170)));
      page = Math.min(page, Math.floor((entries.length - 1) / n));
      const from = page * n, slice = entries.slice(from, from + n);
      body = `<div class="h">
        <div class="strip" aria-hidden="true">${entries.map((_, i) => `<i class="${i >= from && i < from + n ? 'on' : ''}"></i>`).join('')}</div>
        <div class="cols" style="--n:${n}">${slice.map((en, i) => `<div class="col">${entry(en, from + i)}</div>`).join('')}</div>
        <div class="pager">
          <button type="button" class="btn" id="prev" ${page === 0 ? 'disabled' : ''} aria-label="Earlier steps">←</button>
          <span class="pos">${from + 1}–${Math.min(from + n, entries.length)} of ${entries.length}</span>
          <button type="button" class="btn" id="next" ${from + n >= entries.length ? 'disabled' : ''} aria-label="Later steps">→</button>
        </div></div>`;
    } else {
      body = `<div class="v">${entries.slice(0, shown).map((en, i) => `<div class="vi">${entry(en, i)}</div>`).join('')}</div>
        ${shown < entries.length ? `<button type="button" class="btn" id="vmore">Show more (${entries.length - shown} left)</button>` : ''}`;
    }
    root.innerHTML = `
      <h1>${esc(c.title)}</h1>
      ${dates ? `<div class="sub">${esc(dates)}${entries.length ? ` · ${entries.length} steps` : ''}</div>` : ''}
      ${c.summary ? `<p class="sum">${esc(c.summary)}</p>` : ''}
      ${body}
      <div class="actions"><button type="button" class="btn primary" data-open="${esc(c.atlas_url)}">Open chronicle in atlas</button></div>`;
    wire(root);
    $('#prev')?.addEventListener('click', () => { page--; draw(); });
    $('#next')?.addEventListener('click', () => { page++; draw(); });
    $('#vmore')?.addEventListener('click', () => { shown += 5; draw(); });
  }

  app.onToolResult((result) => {
    const sc = result?.structuredContent;
    if (!sc?.chronicle) {
      root.innerHTML = `<p class="msg">${esc(result?.content?.find((c) => c.type === 'text')?.text || 'No chronicle to show.')}</p>`;
      return;
    }
    data = { chronicle: sc.chronicle, entries: sc.entries || [] };
    page = 0; shown = 5; expanded.clear();
    draw();
  });

  let lastMode = null;
  new ResizeObserver(() => {
    const mode = document.documentElement.clientWidth >= 520 ? 'h' : 'v';
    const cols = Math.floor((document.documentElement.clientWidth - 28) / 170);
    const key = mode + cols;
    if (lastMode !== null && key !== lastMode) draw();
    lastMode = key;
  }).observe(document.documentElement);
});
@endverbatim
        </script>
    </x-slot:head>

    <div id="root"><p class="msg">Loading chronicle…</p></div>
</x-mcp::app>
