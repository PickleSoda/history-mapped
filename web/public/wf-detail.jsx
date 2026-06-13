// wf-detail.jsx — entity detail panel variants + timeline scrubber variants
const { cx, GROUPS, GROUP_ORDER, Btn, Badge, Dot, Card, Sep, Tabs, Sk, SkText, Icon, StatCell, ConnRow } = window;

function PanelHead({ group, acts = true }) {
  return (
    <div className="detail-bar">
      <button className="link-back"><Icon name="left" size={15} /> Back</button>
      {acts && <div className="detail-acts">
        <Btn variant="ghost" size="icon" className="sz-sm"><Icon name="bookmark" size={15} /></Btn>
        <Btn variant="ghost" size="icon" className="sz-sm"><Icon name="share" size={15} /></Btn>
      </div>}
    </div>
  );
}
function PanelTitle({ group }) {
  return (
    <div className="aside-pad detail-top">
      <Badge group={group} />
      <Sk h={20} w="80%" r={6} style={{ marginTop: 12 }} />
      <Sk h={11} w="50%" style={{ marginTop: 9 }} />
    </div>
  );
}

// D1 — stats-first
function PanelStats({ group = 'polity' }) {
  return (
    <div className="aside-body">
      <PanelHead group={group} />
      <PanelTitle group={group} />
      <Sep />
      <div className="aside-pad">
        <div className="stat-grid three">
          <StatCell label="Founded" val="550 BCE" />
          <StatCell label="Dissolved" val="330 BCE" />
          <StatCell label="Duration" val="220 yrs" />
          <StatCell label="Capital" val="Persepolis" />
          <StatCell label="Area pk." val="5.5M km²" />
          <StatCell label="Type" val="Empire" />
        </div>
      </div>
      <Sep />
      <div className="aside-pad"><h4 className="sect-h">Summary</h4><SkText lines={4} last="46%" /></div>
      <Sep />
      <div className="aside-pad">
        <h4 className="sect-h">Connections <span className="count">5</span></h4>
        <div className="conn-list"><ConnRow g="place" /><ConnRow g="event" /><ConnRow g="culture" /></div>
      </div>
      <div className="aside-foot"><Icon name="list" size={13} /> 8 sources</div>
    </div>
  );
}

// D2 — prose / narrative first
function PanelProse({ group = 'culture' }) {
  return (
    <div className="aside-body">
      <PanelHead group={group} />
      <div className="aside-pad detail-top">
        <Badge group={group} />
        <Sk h={22} w="86%" r={6} style={{ marginTop: 12 }} />
        <div className="prose-hero"><Icon name="clock" size={14} /><span className="mono">5th c. BCE — 4th c. BCE</span></div>
      </div>
      <Sep />
      <div className="aside-pad"><SkText lines={6} last="58%" /></div>
      <div className="aside-pad pullquote"><Sk h={11} w="92%" /><Sk h={11} w="74%" style={{ marginTop: 8 }} /></div>
      <div className="aside-pad"><SkText lines={4} last="40%" /></div>
      <Sep />
      <div className="aside-pad">
        <div className="inline-stats">
          <span className="istat"><span className="istat-l">Origin</span><span className="mono">Attica</span></span>
          <span className="istat"><span className="istat-l">Peak</span><span className="mono">450 BCE</span></span>
          <span className="istat"><span className="istat-l">Sources</span><span className="mono">12</span></span>
        </div>
      </div>
    </div>
  );
}

// D3 — tabbed
function PanelTabbed({ group = 'place' }) {
  return (
    <div className="aside-body">
      <PanelHead group={group} />
      <PanelTitle group={group} />
      <div className="aside-pad" style={{ paddingTop: 0 }}>
        <Tabs items={['Overview', 'Connections', 'Sources']} active="Overview" className="full-tabs" />
      </div>
      <Sep />
      <div className="aside-pad">
        <div className="detail-chips" style={{ marginTop: 0, marginBottom: 14 }}>
          <span className="meta-chip"><Icon name="clock" size={13} /><span className="mono">c. 515 BCE</span></span>
          <span className="meta-chip"><Icon name="pin" size={13} /> 37.9°N, 23.7°E</span>
        </div>
        <SkText lines={5} last="52%" />
      </div>
      <Sep />
      <div className="aside-pad">
        <div className="stat-grid"><StatCell label="Modern name" val="—" /><StatCell label="Population" val="~30k" /></div>
      </div>
      <div className="aside-foot"><Icon name="list" size={13} /> 4 sources · OHM id 18223</div>
    </div>
  );
}

// =======================================================================
// Timeline scrubber variants
// =======================================================================
function TLFrame({ year, era, locked, children }) {
  return (
    <div className="tl tl-standalone">
      <button className="tl-play"><Icon name="play" size={16} /></button>
      <div className="tl-read"><span className="mono tl-year">{year}{locked && <Icon name="clock" size={12} className="tl-lock" />}</span><span className="tl-era">{era}</span></div>
      <div className="tl-track">{children}</div>
      <div className="tl-zoom"><Btn variant="outline" size="icon" className="sz-sm"><Icon name="minus" size={14} /></Btn><Btn variant="outline" size="icon" className="sz-sm"><Icon name="plus" size={14} /></Btn></div>
    </div>
  );
}

// T1 classic ticks + era bands
function ScrubClassic() {
  return (
    <TLFrame year="490 BCE" era="Classical Antiquity">
      <div className="tl-bands">
        <span style={{ flex: 3, background: 'var(--g-polity-bg)' }} /><span style={{ flex: 4, background: 'var(--g-economy-bg)' }} />
        <span style={{ flex: 2.4, background: 'var(--g-culture-bg)' }} /><span style={{ flex: 3, background: 'var(--g-place-bg)' }} />
      </div>
      <div className="tl-ticks">{Array.from({ length: 28 }).map((_, i) => <span key={i} className={cx('tk', i % 4 === 0 && 'tk-lg')} />)}</div>
      <div className="tl-handle" style={{ left: '34%' }}><span className="tl-knob" /></div>
      <div className="tl-axis"><span className="mono">800 BCE</span><span className="mono">1 CE</span><span className="mono">800 CE</span></div>
    </TLFrame>
  );
}

// T2 density histogram
const HIST = [3,4,5,4,6,7,9,8,6,7,10,12,11,9,8,6,5,7,9,11,13,12,10,8,6,5,4,6,8,7,5,4,3,5,6,8,9,7,6,5,4,3,2,4,5,6,4,3];
function ScrubHistogram() {
  const max = Math.max(...HIST);
  return (
    <TLFrame year="490 BCE" era="Classical Antiquity">
      <div className="tl-hist">
        {HIST.map((v, i) => {
          const g = GROUP_ORDER[i % 5];
          return <span key={i} className="hbar" style={{ height: (v / max) * 100 + '%', background: i / HIST.length < 0.34 ? GROUPS[g].v : 'var(--muted-foreground)', opacity: i / HIST.length < 0.34 ? 0.85 : 0.28 }} />;
        })}
      </div>
      <div className="tl-handle hist" style={{ left: '34%' }}><span className="tl-knob" /></div>
      <div className="tl-axis"><span className="mono">800 BCE</span><span className="mono">1 CE</span><span className="mono">800 CE</span></div>
    </TLFrame>
  );
}

// T3 era bands + range window
function ScrubRange() {
  return (
    <TLFrame year="520 – 450 BCE" era="Range select">
      <div className="tl-bands tall">
        <span style={{ flex: 3, background: 'var(--g-polity-bg)' }}><b>Archaic</b></span>
        <span style={{ flex: 4, background: 'var(--g-economy-bg)' }}><b>Classical</b></span>
        <span style={{ flex: 2.4, background: 'var(--g-culture-bg)' }}><b>Hellenistic</b></span>
        <span style={{ flex: 3, background: 'var(--g-place-bg)' }}><b>Roman</b></span>
      </div>
      <div className="tl-window" style={{ left: '28%', right: '50%' }}>
        <span className="tl-handle range" style={{ left: 0 }}><span className="tl-knob" /></span>
        <span className="tl-handle range" style={{ right: 0 }}><span className="tl-knob" /></span>
      </div>
      <div className="tl-axis"><span className="mono">800 BCE</span><span className="mono">1 CE</span><span className="mono">800 CE</span></div>
    </TLFrame>
  );
}

Object.assign(window, { PanelStats, PanelProse, PanelTabbed, ScrubClassic, ScrubHistogram, ScrubRange });
