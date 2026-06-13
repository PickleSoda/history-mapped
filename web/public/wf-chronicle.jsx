// wf-chronicle.jsx — chronicle tour: scrollytelling layout (single sticky map)
const { cx, GROUPS, Badge, Sk, SkText, Icon, MapBase, Pin } = window;

const CSTEPS = [
  { date: 'c. 559 BCE', g: 'polity', place: 'Anshan, Persis', tag: 'Accession' },
  { date: '550 BCE',    g: 'event',  place: 'Ecbatana',       tag: 'Conquest' },
  { date: '546 BCE',    g: 'place',  place: 'Sardis, Lydia',  tag: 'Annexation' },
];

function ChronTop() {
  return (
    <div className="cdoc-top">
      <button className="link-back"><Icon name="left" size={15} /> Exit tour</button>
      <Badge variant="outline"><Icon name="route" size={12} /> Chronicle</Badge>
      <span className="cdoc-title">Rise of the Achaemenids</span>
      <div className="cdoc-progress" />
      <span className="cdoc-step-count">3 / 8</span>
    </div>
  );
}

// C2 — scrollytelling: narrative beats scroll on the left, ONE map stays sticky
function ChronicleSticky() {
  return (
    <div className="chron-doc">
      <ChronTop />
      <div className="cdoc-body stickymode">
        <div className="cscroll">
          {CSTEPS.map((s, i) => (
            <div className={cx('cbeat', i === 1 && 'is-active')} key={i}>
              <span className="cbeat-date">{s.date}</span>
              <div className="cbeat-meta"><Badge group={s.g}>{s.tag}</Badge><span className="cmeta-row"><Icon name="pin" size={12} /> {s.place}</span></div>
              <Sk h={15} w="68%" r={5} style={{ margin: '13px 0 12px' }} />
              <SkText lines={5} last="48%" />
            </div>
          ))}
        </div>
        <div className="csticky">
          <div className="minimap" style={{ height: '82%', width: '100%' }}>
            <MapBase />
            <div className="map-overlay">
              <Pin group="polity" x={30} y={52} />
              <Pin group="event" x={48} y={42} selected />
              <Pin group="place" x={62} y={38} />
            </div>
            <div className="csticky-chip"><span className="mono">546 BCE</span> · Step 2 of 8</div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ChronicleSticky });
