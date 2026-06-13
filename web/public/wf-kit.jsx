// wf-kit.jsx — shadcn-flavored low-fi wireframe atoms + map placeholder
const { useState } = React;

const cx = (...a) => a.filter(Boolean).join(' ');

// Five entity groups (muted cartographic accents)
const GROUPS = {
  polity:  { label: 'Polity',  v: 'var(--g-polity)',  bg: 'var(--g-polity-bg)'  },
  place:   { label: 'Place',   v: 'var(--g-place)',   bg: 'var(--g-place-bg)'   },
  event:   { label: 'Event',   v: 'var(--g-event)',   bg: 'var(--g-event-bg)'   },
  economy: { label: 'Economy', v: 'var(--g-economy)', bg: 'var(--g-economy-bg)' },
  culture: { label: 'Culture', v: 'var(--g-culture)', bg: 'var(--g-culture-bg)' },
};
const GROUP_ORDER = ['polity', 'place', 'event', 'economy', 'culture'];

function Btn({ variant = 'default', size = 'default', className, children, ...p }) {
  return (
    <button className={cx('wf-btn', 'is-' + variant, size !== 'default' && 'sz-' + size, className)} {...p}>
      {children}
    </button>
  );
}

function Badge({ group, variant, className, children }) {
  const g = group ? GROUPS[group] : null;
  const style = g ? { background: g.bg, color: g.v } : undefined;
  return (
    <span className={cx('wf-badge', variant === 'outline' && 'outline', className)} style={style}>
      {g && <span className="dot" style={{ background: g.v }} />}
      {children ?? (g ? g.label : null)}
    </span>
  );
}

function Dot({ group, className, style }) {
  const g = group ? GROUPS[group] : null;
  return <span className={cx('dot', className)} style={{ background: g ? g.v : 'var(--muted-foreground)', ...style }} />;
}

function Card({ className, children, style }) {
  return <div className={cx('wf-card', className)} style={style}>{children}</div>;
}

function Sep({ vertical, className, style }) {
  return <div className={cx('wf-sep', vertical && 'v', className)} style={style} />;
}

function Input({ className, ...p }) {
  return <input className={cx('wf-input', className)} {...p} />;
}

function Tabs({ items, active, onChange, className }) {
  const [a, setA] = useState(active ?? items[0]);
  const cur = active ?? a;
  return (
    <div className={cx('wf-tabs', className)}>
      {items.map((it) => (
        <button key={it} className={cx('wf-tab', cur === it && 'is-active')}
          onClick={() => { setA(it); onChange && onChange(it); }}>{it}</button>
      ))}
    </div>
  );
}

// Skeleton placeholders --------------------------------------------------
function Sk({ w, h, r, className, style }) {
  return <div className={cx('sk', className)} style={{ width: w, height: h, borderRadius: r, ...style }} />;
}
function SkText({ lines = 3, gap = 9, last = '70%', className }) {
  const ws = ['100%', '94%', '88%', '96%', '82%', '91%'];
  return (
    <div className={cx(className)} style={{ display: 'flex', flexDirection: 'column', gap }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Sk key={i} h={9} w={i === lines - 1 ? last : ws[i % ws.length]} />
      ))}
    </div>
  );
}

function Kbd({ children }) { return <kbd className="wf-kbd">{children}</kbd>; }

// Map placeholder --------------------------------------------------------
function MapBase() {
  // low-fi cartographic stand-in: graticule + abstract landmasses
  return (
    <svg className="map-svg" viewBox="0 0 1000 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <pattern id="grat" width="62" height="62" patternUnits="userSpaceOnUse">
          <path d="M62 0H0V62" fill="none" stroke="var(--map-grid)" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="1000" height="640" fill="var(--map-water)" />
      <rect width="1000" height="640" fill="url(#grat)" />
      <g fill="var(--map-land)" stroke="var(--map-coast)" strokeWidth="1.5" strokeDasharray="2 4">
        <path d="M120 150 C 90 220 130 300 110 380 C 200 430 300 410 360 350 C 410 300 380 220 320 180 C 250 130 170 110 120 150 Z" />
        <path d="M520 120 C 470 180 500 250 560 270 C 640 295 720 260 760 200 C 800 140 740 90 660 90 C 590 90 555 95 520 120 Z" />
        <path d="M600 360 C 560 410 580 480 650 510 C 740 545 840 500 870 430 C 895 370 840 330 760 335 C 690 339 640 330 600 360 Z" />
        <path d="M250 470 C 230 510 260 560 320 560 C 380 560 410 520 395 480 C 380 445 300 440 250 470 Z" />
      </g>
    </svg>
  );
}

function MapCanvas({ year, era, dim, children, className }) {
  return (
    <div className={cx('map-canvas', dim && 'is-dim', className)}>
      <MapBase />
      <div className="map-overlay">{children}</div>
      {(year || era) && (
        <div className="map-year">
          {era && <span className="map-era">{era}</span>}
          {year && <span className="map-year-num">{year}</span>}
        </div>
      )}
      <div className="map-attrib">OpenHistoricalMap · basemap placeholder</div>
    </div>
  );
}

// A teardrop pin placed by % coords on a relative parent
function Pin({ group = 'place', x, y, selected, label }) {
  const g = GROUPS[group];
  return (
    <div className={cx('pin', selected && 'selected')} style={{ left: x + '%', top: y + '%' }}>
      {label && <span className="pin-label">{label}</span>}
      <span className="pin-head" style={{ background: g.v, boxShadow: selected ? `0 0 0 4px ${g.bg}` : undefined }}>
        <span className="pin-dot" />
      </span>
    </div>
  );
}

Object.assign(window, {
  cx, GROUPS, GROUP_ORDER,
  Btn, Badge, Dot, Card, Sep, Input, Tabs, Sk, SkText, Kbd,
  MapBase, MapCanvas, Pin,
});
