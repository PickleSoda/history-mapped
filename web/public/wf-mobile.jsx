// wf-mobile.jsx — mobile bottom-sheet behavior states
const { cx, GROUPS, GROUP_ORDER, Badge, Dot, Sep, Sk, SkText, Input, Icon, MapCanvas, ScatterPins, StatCell, ConnRow } = window;

function Phone({ children }) {
  return (
    <div className="phone">
      <div className="phone-status"><span className="mono">9:41</span><span className="phone-dots"><i /><i /><i /></span></div>
      <div className="phone-screen">{children}</div>
      <div className="phone-home" />
    </div>
  );
}

function MTop() {
  return (
    <div className="m-top">
      <button className="m-search"><Icon name="search" size={15} /><span className="omni-ph">Search the atlas…</span></button>
      <button className="m-fab"><Icon name="sliders" size={16} /></button>
    </div>
  );
}
function MTimeline() {
  return (
    <div className="m-timeline">
      <span className="mono m-year">490 BCE</span>
      <div className="m-track"><span className="m-knob" style={{ left: '36%' }} /></div>
      <button className="m-play"><Icon name="play" size={13} /></button>
    </div>
  );
}
function MGrabber() { return <div className="m-grab" />; }
function MChips() {
  return (
    <div className="m-chips">
      {GROUP_ORDER.map((g, i) => (
        <button key={g} className={cx('chip', i < 2 && 'is-on')} style={i < 2 ? { background: GROUPS[g].v + '1f', color: GROUPS[g].v } : undefined}>
          <span className="dot" style={{ background: GROUPS[g].v }} /> {GROUPS[g].label}
        </button>
      ))}
    </div>
  );
}
function MRow({ g, span, w }) {
  return (
    <div className="m-row">
      <span className="dot" style={{ background: GROUPS[g].v }} />
      <span className="m-row-main"><Sk h={10} w={w} /><span className="m-row-meta"><Badge group={g} /><span className="mono m-span">{span}</span></span></span>
      <Icon name="right" size={14} className="lrow-chev" />
    </div>
  );
}

// M1 — collapsed peek
function MobilePeek() {
  return (
    <Phone>
      <div className="m-map"><MapCanvas year="490 BCE" era="Classical"><ScatterPins selectedIdx={-1} /></MapCanvas></div>
      <MTop />
      <MTimeline />
      <div className="m-sheet peek">
        <MGrabber />
        <div className="m-sheet-head"><span className="m-sheet-title">Within view</span><span className="mono muted-fg">248</span></div>
        <MChips />
        <Sep style={{ margin: '12px 0 6px' }} />
        <MRow g="event" span="490 BCE" w="58%" />
      </div>
    </Phone>
  );
}

// M2 — half sheet (browse)
function MobileHalf() {
  return (
    <Phone>
      <div className="m-map short"><MapCanvas year="490 BCE" era="Classical"><ScatterPins /></MapCanvas></div>
      <MTop />
      <div className="m-sheet half">
        <MGrabber />
        <div className="m-sheet-pad"><div className="aside-search"><Icon name="search" size={14} className="asx" /><Input placeholder="Filter…" style={{ paddingLeft: 32 }} /></div></div>
        <MChips />
        <Sep style={{ margin: '12px 0 2px' }} />
        <div className="m-list">
          <MRow g="polity" span="550–330 BCE" w="64%" />
          <MRow g="event" span="490 BCE" w="50%" />
          <MRow g="place" span="c. 515 BCE" w="58%" />
          <MRow g="economy" span="6th c. BCE" w="46%" />
          <MRow g="culture" span="5th c. BCE" w="60%" />
        </div>
      </div>
    </Phone>
  );
}

// M3 — full sheet detail
function MobileFull() {
  return (
    <Phone>
      <div className="m-map tiny"><MapCanvas year="490 BCE" era="Classical"><ScatterPins selectedIdx={1} dimOthers /></MapCanvas></div>
      <div className="m-sheet full">
        <MGrabber />
        <div className="m-detail-bar"><button className="link-back"><Icon name="left" size={15} /> Results</button><div className="detail-acts"><Icon name="bookmark" size={16} /><Icon name="share" size={16} /></div></div>
        <div className="m-sheet-pad">
          <Badge group="event" />
          <Sk h={19} w="74%" r={6} style={{ marginTop: 11 }} />
          <div className="detail-chips"><span className="meta-chip"><Icon name="clock" size={13} /><span className="mono">490 BCE</span></span><span className="meta-chip"><Icon name="pin" size={13} /> Marathon</span></div>
        </div>
        <Sep />
        <div className="m-sheet-pad"><div className="stat-grid"><StatCell label="Began" val="490 BCE" /><StatCell label="Type" val="Battle" /></div></div>
        <Sep />
        <div className="m-sheet-pad"><h4 className="sect-h">Overview</h4><SkText lines={4} last="44%" /></div>
        <Sep />
        <div className="m-sheet-pad"><h4 className="sect-h">Connections <span className="count">3</span></h4><div className="conn-list"><ConnRow g="polity" /><ConnRow g="polity" /></div></div>
      </div>
    </Phone>
  );
}

Object.assign(window, { Phone, MobilePeek, MobileHalf, MobileFull });
