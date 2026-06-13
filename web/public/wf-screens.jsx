// wf-screens.jsx — desktop shell + core/selection/chronicle screens
const { cx, GROUPS, GROUP_ORDER, Btn, Badge, Dot, Card, Sep, Input, Tabs, Sk, SkText, Kbd, MapCanvas, Pin } = window;

// --- tiny lucide-ish icon set ------------------------------------------
const IP = {
  search: 'M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z',
  layers: 'M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5',
  play: 'M7 5l11 7-11 7z',
  pause: 'M8 5v14M16 5v14',
  clock: 'M12 7v5l3 2M12 21a9 9 0 100-18 9 9 0 000 18z',
  left: 'M15 18l-6-6 6-6',
  right: 'M9 18l6-6-6-6',
  x: 'M18 6L6 18M6 6l12 12',
  bookmark: 'M6 4h12v16l-6-4-6 4z',
  sliders: 'M4 6h10M18 6h2M4 12h2M10 12h10M4 18h7M15 18h5M14 4v4M8 10v4M19 16v4',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  pin: 'M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  compass: 'M12 21a9 9 0 100-18 9 9 0 000 18zM15.5 8.5l-2 5-5 2 2-5 5-2z',
  route: 'M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM8 17h6a3 3 0 003-3V9',
  sparkle: 'M12 4l1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6z',
  globe: 'M12 21a9 9 0 100-18 9 9 0 000 18zM3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18',
  up: 'M12 19V5M5 12l7-7 7 7',
  share: 'M12 16V4M8 8l4-4 4 4M5 14v4a2 2 0 002 2h10a2 2 0 002-2v-4',
  grip: 'M9 6h.01M9 12h.01M9 18h.01M15 6h.01M15 12h.01M15 18h.01',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
};
function Icon({ name, size = 16, className, style }) {
  return (
    <svg className={cx('ic', className)} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" style={style}>
      <path d={IP[name] || ''} />
    </svg>
  );
}

// --- top bar ------------------------------------------------------------
function YearNav() {
  return (
    <div className="yearnav">
      <button className="yearnav-b"><Icon name="left" size={15} /></button>
      <span className="mono yearnav-y">490 BCE</span>
      <button className="yearnav-b"><Icon name="right" size={15} /></button>
      <span className="yearnav-era">Classical</span>
    </div>
  );
}
function TopBar() {
  return (
    <div className="shell-topbar">
      <div className="brand">
        <span className="brand-mark"><Icon name="compass" size={17} /></span>
        <span className="brand-name">ATLAS</span>
        <Badge variant="outline" className="brand-tag">Historical</Badge>
      </div>
      <div className="topbar-center">
        <button className="omni">
          <Icon name="search" size={15} />
          <span className="omni-ph">Search places, polities, events…</span>
          <Kbd>⌘K</Kbd>
        </button>
        <YearNav />
      </div>
      <div className="topbar-right">
        <div className="seg">
          <button className="seg-b is-on"><Icon name="pin" size={14} /> Map</button>
          <button className="seg-b"><Icon name="globe" size={14} /> Globe</button>
        </div>
        <Btn variant="ghost" size="icon"><Icon name="layers" /></Btn>
        <Btn variant="ghost" size="icon"><Icon name="sliders" /></Btn>
        <span className="avatar" />
      </div>
    </div>
  );
}

// --- browse aside -------------------------------------------------------
const ENTS = [
  ['polity', '550–330 BCE', 3], ['event', '490 BCE', 3], ['place', 'c. 515 BCE', 2],
  ['polity', '478–404 BCE', 3], ['economy', '6th c. BCE', 2], ['culture', '5th c. BCE', 2],
  ['event', '480 BCE', 1],
];
function FilterChips() {
  return (
    <div className="chips">
      {GROUP_ORDER.map((g, i) => (
        <button key={g} className={cx('chip', i < 3 && 'is-on')} style={i < 3 ? { '--c': GROUPS[g].v, background: GROUPS[g].bg, color: GROUPS[g].v } : undefined}>
          <span className="dot" style={{ background: GROUPS[g].v }} /> {GROUPS[g].label}
        </button>
      ))}
    </div>
  );
}
function ListRow({ g, span, w = '72%', prom = 2, selected }) {
  return (
    <button className={cx('lrow', selected && 'is-sel')}>
      <span className="dot lrow-dot" style={{ background: GROUPS[g].v }} />
      <span className="lrow-main">
        <Sk h={10} w={w} />
        <span className="lrow-meta"><Badge group={g} /><span className="mono lrow-span">{span}</span></span>
      </span>
      <span className={cx('prom', 'p' + prom)} title="Prominence in this period & scope"><i /><i /><i /></span>
    </button>
  );
}
function BrowseList({ activeTab = 'Browse' }) {
  return (
    <div className="aside-body">
      <div className="aside-head">
        <Tabs items={['Browse', 'Chronicles', 'Selection']} active={activeTab} />
      </div>
      <div className="aside-pad">
        <div className="aside-search"><Icon name="search" size={14} className="asx" /><Input placeholder="Filter within view…" style={{ paddingLeft: 32 }} /></div>
        <FilterChips />
        <div className="scope-note"><Icon name="clock" size={12} /> 490–480 BCE <span className="scope-dot">·</span> <Icon name="pin" size={12} /> current view</div>
      </div>
      <Sep />
      <div className="aside-subhead"><span className="subhead-l"><Icon name="sparkle" size={13} /> Notable here</span><span className="mono muted-fg">top 7</span></div>
      <div className="list">
        {ENTS.map((e, i) => <ListRow key={i} g={e[0]} span={e[1]} prom={e[2]} w={['78%','64%','71%','58%','82%','66%','74%'][i]} selected={i === 1} />)}
      </div>
      <button className="list-more">Show all 248 in scope <Icon name="right" size={14} /></button>
    </div>
  );
}

// --- inline detail (selection screens) ----------------------------------
function StatCell({ label, val }) {
  return (
    <div className="stat-cell">
      <span className="stat-label">{label}</span>
      <span className="mono stat-val">{val}</span>
    </div>
  );
}
function ConnRow({ g }) {
  return (
    <div className="conn-row">
      <span className="dot" style={{ background: GROUPS[g].v }} />
      <Sk h={9} w="62%" />
      <Badge group={g} className="conn-badge" />
    </div>
  );
}
function InlineDetail({ group = 'event', placed = true }) {
  return (
    <div className="aside-body">
      <div className="detail-bar">
        <button className="link-back"><Icon name="left" size={15} /> Back to results</button>
        <div className="detail-acts">
          <Btn variant="ghost" size="icon" className="sz-sm"><Icon name="bookmark" size={15} /></Btn>
          <Btn variant="ghost" size="icon" className="sz-sm"><Icon name="share" size={15} /></Btn>
        </div>
      </div>
      <div className="aside-pad detail-top">
        <Badge group={group} />
        <Sk h={20} w="78%" r={6} style={{ marginTop: 12 }} />
        <Sk h={11} w="52%" style={{ marginTop: 9 }} />
        <div className="detail-chips">
          <span className="meta-chip"><Icon name="clock" size={13} /><span className="mono">490 BCE</span></span>
          {placed
            ? <span className="meta-chip"><Icon name="pin" size={13} /> Marathon, Attica</span>
            : <span className="meta-chip warn"><Icon name="pin" size={13} /> Not placed on map</span>}
        </div>
      </div>
      <Sep />
      <div className="aside-pad">
        <div className="stat-grid">
          <StatCell label="Began" val="490 BCE" />
          <StatCell label="Ended" val="490 BCE" />
          <StatCell label="Belligerents" val="2" />
          <StatCell label="Confidence" val="High" />
        </div>
      </div>
      <Sep />
      <div className="aside-pad">
        <h4 className="sect-h">Overview</h4>
        <SkText lines={5} last="48%" />
      </div>
      <Sep />
      <div className="aside-pad">
        <h4 className="sect-h">Connections <span className="count">3</span></h4>
        <div className="conn-list"><ConnRow g="polity" /><ConnRow g="polity" /><ConnRow g="place" /></div>
      </div>
      <div className="aside-foot"><Icon name="list" size={13} /> 4 sources · last edited 2024</div>
    </div>
  );
}

// --- timeline (classic, used as shell default) --------------------------
function TimelineClassic({ year = '490 BCE', era = 'Classical Antiquity', locked }) {
  return (
    <div className="tl">
      <button className="tl-play"><Icon name="play" size={16} /></button>
      <div className="tl-read">
        <span className="mono tl-year">{year}{locked && <Icon name="clock" size={12} className="tl-lock" />}</span>
        <span className="tl-era">{era}</span>
      </div>
      <div className="tl-track">
        <div className="tl-bands">
          <span style={{ flex: 3, background: 'var(--g-polity-bg)' }} />
          <span style={{ flex: 4, background: 'var(--g-economy-bg)' }} />
          <span style={{ flex: 2.4, background: 'var(--g-culture-bg)' }} />
          <span style={{ flex: 3, background: 'var(--g-place-bg)' }} />
        </div>
        <div className="tl-ticks">{Array.from({ length: 28 }).map((_, i) => <span key={i} className={cx('tk', i % 4 === 0 && 'tk-lg')} />)}</div>
        <div className="tl-handle" style={{ left: '34%' }}><span className="tl-knob" /></div>
        <div className="tl-axis"><span className="mono">800 BCE</span><span className="mono">1 CE</span><span className="mono">800 CE</span></div>
      </div>
      <div className="tl-zoom">
        <Btn variant="outline" size="icon" className="sz-sm"><Icon name="minus" size={14} /></Btn>
        <Btn variant="outline" size="icon" className="sz-sm"><Icon name="plus" size={14} /></Btn>
      </div>
    </div>
  );
}

// --- map overlays -------------------------------------------------------
function ScatterPins({ selectedIdx = -1, dimOthers }) {
  const pts = [[28, 40, 'polity'], [44, 30, 'event'], [58, 52, 'place'], [70, 38, 'economy'], [38, 60, 'culture'], [62, 24, 'polity']];
  return pts.map((p, i) => (
    <div key={i} style={{ opacity: dimOthers && i !== selectedIdx ? 0.35 : (i === selectedIdx ? 1 : 0.85) }}>
      <Pin group={p[2]} x={p[0]} y={p[1]} selected={i === selectedIdx} />
    </div>
  ));
}
function TerritoryOverlay({ group = 'polity' }) {
  const g = GROUPS[group];
  return (
    <>
      <svg className="terr-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d="M30 28 C 22 38 26 52 34 58 C 46 66 62 60 68 50 C 74 40 70 28 60 24 C 48 19 38 20 30 28 Z"
          fill={g.v} fillOpacity="0.16" stroke={g.v} strokeWidth="0.5" strokeDasharray="1.4 1.2" />
      </svg>
      <div className="terr-chip" style={{ left: '46%', top: '40%', color: g.v, borderColor: g.v, background: g.bg }}>
        <span className="dot" style={{ background: g.v }} /> Extent · 480 BCE
      </div>
    </>
  );
}

// =======================================================================
// Screen compositions
// =======================================================================
function DesktopShell({ side = 'right', aside, overlay, timeline, year, era, dim, banner }) {
  return (
    <div className="shell">
      <TopBar />
      <div className="shell-body">
        <div className="shell-main">
          <MapCanvas year={year ?? '490 BCE'} era={era ?? 'Classical Antiquity'} dim={dim}>{overlay}</MapCanvas>
          {banner}
        </div>
        <aside className={cx('shell-aside', side === 'left' && 'left')}>{aside ?? <BrowseList />}</aside>
      </div>
      <div className="shell-timeline">{timeline ?? <TimelineClassic />}</div>
    </div>
  );
}

// Shell options
function ShellRight() { return <DesktopShell side="right" overlay={<ScatterPins />} />; }
function ShellLeft() { return <DesktopShell side="left" overlay={<ScatterPins />} />; }
function ShellFloat() {
  return (
    <div className="shell shell-float">
      <MapCanvas year="490 BCE" era="Classical Antiquity"><ScatterPins /></MapCanvas>
      <div className="fl-topleft"><span className="brand-mark"><Icon name="compass" size={16} /></span><span className="brand-name">ATLAS</span></div>
      <button className="fl-search omni"><Icon name="search" size={15} /><span className="omni-ph">Search…</span><Kbd>⌘K</Kbd></button>
      <div className="fl-tools"><Btn variant="outline" size="icon"><Icon name="layers" /></Btn><Btn variant="outline" size="icon"><Icon name="sliders" /></Btn></div>
      <Card className="fl-aside"><BrowseList /></Card>
      <Card className="fl-timeline"><TimelineClassic /></Card>
    </div>
  );
}

// Shell option D — list left, map center, detail + timeline right
function MiniTimeline({ year = '490 BCE', era = 'Classical Antiquity' }) {
  return (
    <div className="mtl">
      <div className="mtl-top">
        <button className="tl-play sm"><Icon name="play" size={13} /></button>
        <div className="mtl-read"><span className="mono mtl-year">{year}</span><span className="mtl-era">{era}</span></div>
        <div className="mtl-zoom"><Btn variant="outline" size="icon" className="sz-sm"><Icon name="minus" size={13} /></Btn><Btn variant="outline" size="icon" className="sz-sm"><Icon name="plus" size={13} /></Btn></div>
      </div>
      <div className="mtl-track">
        <div className="tl-bands"><span style={{ flex: 3, background: 'var(--g-polity-bg)' }} /><span style={{ flex: 4, background: 'var(--g-economy-bg)' }} /><span style={{ flex: 2.4, background: 'var(--g-culture-bg)' }} /><span style={{ flex: 3, background: 'var(--g-place-bg)' }} /></div>
        <div className="tl-handle" style={{ left: '34%' }}><span className="tl-knob" /></div>
        <div className="tl-axis"><span className="mono">800 BCE</span><span className="mono">1 CE</span><span className="mono">800 CE</span></div>
      </div>
    </div>
  );
}
function ShellListDetail() {
  return (
    <div className="shell">
      <TopBar />
      <div className="shell-body">
        <aside className="shell-rail"><BrowseList /></aside>
        <div className="shell-main"><MapCanvas year="490 BCE" era="Classical Antiquity"><ScatterPins selectedIdx={1} dimOthers /></MapCanvas></div>
        <aside className="shell-detail">
          <div className="rail-timeline"><MiniTimeline /></div>
          <InlineDetail group="event" />
        </aside>
      </div>
    </div>
  );
}

// Core screens
function ScreenDefault() { return <DesktopShell side="right" overlay={<ScatterPins />} />; }

function ScreenSearch() {
  return (
    <div className="shell screen-rel">
      <DesktopShell side="right" overlay={<ScatterPins dimOthers />} dim />
      <div className="cmd-backdrop">
        <Card className="cmd">
          <div className="cmd-input"><Icon name="search" size={17} /><span className="cmd-ph">marathon</span><span className="cmd-caret" /><button className="cmd-x"><Icon name="x" size={14} /></button></div>
          <div className="cmd-filters">
            <button className="chip is-on">All</button>
            {GROUP_ORDER.map((g) => (
              <button key={g} className="chip"><span className="dot" style={{ background: GROUPS[g].v }} /> {GROUPS[g].label}</button>
            ))}
          </div>
          <Sep />
          <div className="cmd-body">
            <div className="cmd-group">Suggestions</div>
            <CmdRow g="event" span="490 BCE" w="40%" active />
            <CmdRow g="place" span="Attica" w="34%" />
            <div className="cmd-group">Polities</div>
            <CmdRow g="polity" span="550–330 BCE" w="46%" />
            <CmdRow g="polity" span="508–322 BCE" w="38%" />
            <div className="cmd-group">Places</div>
            <CmdRow g="place" span="region" w="30%" />
          </div>
          <Sep />
          <div className="cmd-foot"><span><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span><span><Kbd>↵</Kbd> open</span><span><Kbd>esc</Kbd> close</span></div>
        </Card>
      </div>
    </div>
  );
}
function CmdRow({ g, span, w, active }) {
  return (
    <div className={cx('cmd-row', active && 'is-active')}>
      <Icon name="pin" size={15} className="cmd-row-ic" style={{ color: GROUPS[g].v }} />
      <Sk h={10} w={w} />
      <Badge group={g} className="cmd-row-badge" />
      <span className="mono cmd-row-span">{span}</span>
    </div>
  );
}

function ScreenHighlights() {
  const banner = (
    <Card className="ph">
      <div className="ph-head">
        <span className="ph-title"><Icon name="sparkle" size={15} /> Period Highlights</span>
        <span className="mono ph-year">480 BCE</span>
        <button className="ph-x"><Icon name="x" size={14} /></button>
      </div>
      <div className="ph-cards">
        <PhCard g="event" tag="New" />
        <PhCard g="polity" tag="Peak" />
        <PhCard g="culture" tag="New" />
      </div>
    </Card>
  );
  return <DesktopShell side="right" overlay={<ScatterPins />} banner={banner} year="480 BCE" />;
}
function PhCard({ g, tag }) {
  return (
    <div className="ph-card" style={{ borderColor: GROUPS[g].v + '40' }}>
      <div className="ph-card-top"><Dot group={g} /><span className="ph-tag" style={{ color: GROUPS[g].v, background: GROUPS[g].bg }}>{tag}</span></div>
      <Sk h={10} w="84%" style={{ marginTop: 10 }} />
      <Sk h={8} w="56%" style={{ marginTop: 7 }} />
    </div>
  );
}

// Selection states
function ScreenPoint() { return <DesktopShell side="right" aside={<InlineDetail group="event" />} overlay={<ScatterPins selectedIdx={1} dimOthers />} />; }
function ScreenTerritory() { return <DesktopShell side="right" aside={<InlineDetail group="polity" />} overlay={<><TerritoryOverlay group="polity" /><ScatterPins selectedIdx={5} dimOthers /></>} year="480 BCE" />; }
function ScreenNoGeom() {
  return <DesktopShell side="right" aside={<InlineDetail group="culture" placed={false} />} dim
    overlay={<ScatterPins dimOthers />}
    banner={<div className="nogeo-banner"><Icon name="pin" size={14} /> This entity has no mapped location · showing related places</div>} />;
}

// Chronicle tour mid-step
function ScreenChronicle() {
  const aside = (
    <div className="aside-body">
      <div className="aside-head chron-head">
        <button className="link-back"><Icon name="left" size={15} /> Exit tour</button>
        <Badge variant="outline"><Icon name="route" size={12} /> Chronicle</Badge>
      </div>
      <div className="aside-pad">
        <Sk h={16} w="70%" r={5} />
        <div className="chron-progress">
          <span className="mono chron-step">Step 3 / 8</span>
          <div className="chron-dots">{Array.from({ length: 8 }).map((_, i) => <span key={i} className={cx('cdot', i < 3 && 'done', i === 2 && 'cur')} />)}</div>
        </div>
      </div>
      <Sep />
      <div className="aside-pad">
        <Sk h={13} w="55%" r={5} style={{ marginBottom: 12 }} />
        <SkText lines={6} last="42%" />
      </div>
      <Sep />
      <div className="aside-pad">
        <h4 className="sect-h">What changed here</h4>
        <div className="conn-list"><ConnRow g="polity" /><ConnRow g="event" /></div>
      </div>
      <div className="chron-nav">
        <Btn variant="outline"><Icon name="left" size={15} /> Prev</Btn>
        <Btn variant="default" className="grow"><Icon name="right" size={15} /> Next step</Btn>
      </div>
    </div>
  );
  const overlay = (
    <>
      <svg className="route-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d="M30 56 Q 40 30 50 38 T 64 26" fill="none" stroke="var(--g-polity)" strokeWidth="0.5" strokeDasharray="1.6 1.4" opacity="0.7" />
      </svg>
      <ScatterPins selectedIdx={1} dimOthers />
      <Card className="map-callout" style={{ left: '48%', top: '18%' }}>
        <div className="mc-top"><Badge group="event" /><span className="mono mc-year">490 BCE</span></div>
        <Sk h={10} w="80%" style={{ marginTop: 9 }} /><Sk h={8} w="60%" style={{ marginTop: 6 }} />
      </Card>
    </>
  );
  return <DesktopShell side="right" aside={aside} overlay={overlay} timeline={<TimelineClassic year="490 BCE" locked />} />;
}

Object.assign(window, {
  Icon, TopBar, BrowseList, InlineDetail, TimelineClassic, DesktopShell, ScatterPins, TerritoryOverlay, ListRow, ConnRow, StatCell, FilterChips,
  ShellRight, ShellLeft, ShellFloat, ShellListDetail, MiniTimeline, YearNav,
  ScreenDefault, ScreenSearch, ScreenHighlights, ScreenPoint, ScreenTerritory, ScreenNoGeom, ScreenChronicle,
});
