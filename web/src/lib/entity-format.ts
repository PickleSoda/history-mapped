/**
 * Display helpers for entity detail fields — pure, shared by the detail panel
 * and the entity page. The free-form JSON fields (`source_citations`,
 * `media_refs`, `attributes`) have no fixed schema, so these flatten whatever
 * shape arrives into rows the UI can render without trusting it.
 */
import { formatYear } from '@/lib/format';

/** snake_case → "Snake case". */
export function humanise(key: string): string {
  const s = key.replace(/[_-]+/g, ' ').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** A year (number) or raw date string → display text (strings verbatim). */
export function yearText(v: number | string | null): string | null {
  if (v == null) return null;
  return typeof v === 'number' ? formatYear(v) : v;
}

/** Extract a numeric year from a year number or a date string (null if none). */
export function numericYear(v: number | string | null): number | null {
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const m = v.match(/-?\d{1,6}/);
    if (m) return parseInt(m[0], 10);
  }
  return null;
}

/** Short date line: the display range, else start – end, else the era. */
export function temporalText(d: {
  temporal_display_range: string | null;
  temporal_start: number | string | null;
  temporal_end: number | string | null;
  era_label: string | null;
}): string | null {
  if (d.temporal_display_range) return d.temporal_display_range;
  const s = dateText(d.temporal_start);
  const e = dateText(d.temporal_end);
  if (s && e) return `${s} – ${e}`;
  return s ?? e ?? d.era_label ?? null;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * A temporal bound → readable date. Years get the era suffix ("490 BCE");
 * ISO dates read as "2 Jul 1976 CE" / "Jul 1976 CE"; anything else is shown
 * verbatim.
 */
export function dateText(v: number | string | null): string | null {
  if (v == null) return null;
  if (typeof v === 'number') return formatYear(v);
  const m = v.trim().match(/^(-?\d{1,6})(?:-(\d{2}))?(?:-(\d{2}))?$/);
  if (!m) return v;
  const year = formatYear(parseInt(m[1], 10));
  const month = m[2] ? MONTHS[parseInt(m[2], 10) - 1] : undefined;
  const day = m[3] ? parseInt(m[3], 10) : undefined;
  if (!month) return year;
  return day ? `${day} ${month} ${year}` : `${month} ${year}`;
}

/** Whole-year span between two bounds ("214 years"), or null. */
export function spanText(start: number | string | null, end: number | string | null): string | null {
  const a = numericYear(start);
  const b = numericYear(end);
  if (a == null || b == null || b < a) return null;
  const years = b - a;
  if (years === 0) return 'under a year';
  return `${years.toLocaleString()} year${years === 1 ? '' : 's'}`;
}

export interface CitationRow {
  label: string;
  value: string;
  href?: string;
}

const isUrl = (s: string) => /^https?:\/\//i.test(s);

/** Turn a citation key/value into a link where we know how to. */
function citationHref(key: string, value: string): string | undefined {
  if (isUrl(value)) return value;
  if (key === 'wikidata_id' && /^Q\d+$/.test(value)) return `https://www.wikidata.org/wiki/${value}`;
  if (key === 'ohm_feature' && /^(relation|way|node)\/\d+$/.test(value)) {
    return `https://www.openhistoricalmap.org/${value}`;
  }
  return undefined;
}

function scalar(v: unknown): string | null {
  if (v == null || v === '') return null;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  return JSON.stringify(v);
}

/**
 * Flatten `source_citations` into labelled rows. Objects become one row per
 * key (dropping `wikidata_id` when its URL is also present); arrays become one
 * row per item (objects read as {title|label|name, url|href}); strings are a
 * single row.
 */
export function citationRows(value: unknown): CitationRow[] {
  if (value == null) return [];
  if (typeof value === 'string') {
    return value ? [{ label: 'Source', value, href: isUrl(value) ? value : undefined }] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item, i): CitationRow[] => {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        const o = item as Record<string, unknown>;
        const url = scalar(o.url ?? o.href ?? o.link);
        const title = scalar(o.title ?? o.label ?? o.name ?? o.citation);
        if (!url && !title) return [{ label: `Source ${i + 1}`, value: JSON.stringify(o) }];
        return [
          {
            label: title && url ? title : `Source ${i + 1}`,
            value: url ?? (title as string),
            href: url && isUrl(url) ? url : undefined,
          },
        ];
      }
      const s = scalar(item);
      return s ? [{ label: `Source ${i + 1}`, value: s, href: isUrl(s) ? s : undefined }] : [];
    });
  }
  if (typeof value === 'object') {
    const o = value as Record<string, unknown>;
    return Object.entries(o).flatMap(([key, v]): CitationRow[] => {
      if (key === 'wikidata_id' && o.wikidata_url) return [];
      const s = scalar(v);
      if (s == null) return [];
      return [{ label: humanise(key), value: s, href: citationHref(key, s) }];
    });
  }
  const s = scalar(value);
  return s ? [{ label: 'Source', value: s }] : [];
}

export interface MediaItem {
  url: string;
  caption: string | null;
  isImage: boolean;
}

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|avif|svg)(\?.*)?$/i;

/** Flatten `media_refs` (a URL, a list of URLs, or {url, caption, type}
 *  objects) into renderable items. Non-URL junk is skipped. */
export function mediaItems(value: unknown): MediaItem[] {
  const one = (v: unknown): MediaItem | null => {
    if (typeof v === 'string') {
      return isUrl(v) ? { url: v, caption: null, isImage: IMAGE_EXT.test(v) } : null;
    }
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const o = v as Record<string, unknown>;
      const url = scalar(o.url ?? o.src ?? o.href);
      if (!url || !isUrl(url)) return null;
      const kind = scalar(o.type ?? o.kind ?? o.media_type);
      return {
        url,
        caption: scalar(o.caption ?? o.title ?? o.alt ?? o.description),
        isImage: (kind != null && /image|photo/i.test(kind)) || IMAGE_EXT.test(url),
      };
    }
    return null;
  };
  const list = Array.isArray(value) ? value : value == null ? [] : [value];
  return list.map(one).filter((m): m is MediaItem => m !== null);
}

/** Attribute keys already shown elsewhere on the page (or internal). */
const ATTRIBUTE_SKIP = new Set([
  'date_raw',
  'temporal_display_range',
  'era_label',
  'confidence_notes',
  'validation_flags',
  'media_refs',
  'entity_color',
]);

export interface AttributeRow {
  key: string;
  label: string;
  value: string;
}

/** The entity's `attributes` as label/value rows, minus the keys the page
 *  already shows. Lists of scalars join with commas; booleans read Yes/No. */
export function attributeRows(attrs: Record<string, unknown>): AttributeRow[] {
  return Object.entries(attrs).flatMap(([key, v]): AttributeRow[] => {
    if (ATTRIBUTE_SKIP.has(key) || v == null || v === '') return [];
    let value: string;
    if (typeof v === 'boolean') value = v ? 'Yes' : 'No';
    else if (typeof v === 'number') value = v.toLocaleString();
    else if (typeof v === 'string') value = v;
    else if (Array.isArray(v) && v.every((x) => typeof x !== 'object' || x === null)) {
      if (v.length === 0) return [];
      value = v.join(', ');
    } else value = JSON.stringify(v);
    return [{ key, label: humanise(key), value }];
  });
}
