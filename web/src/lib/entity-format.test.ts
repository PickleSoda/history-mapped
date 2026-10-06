import { describe, expect, it } from 'vitest';
import {
  attributeRows,
  citationRows,
  dateText,
  humanise,
  mediaItems,
  numericYear,
  spanText,
  temporalText,
} from './entity-format';

describe('dates', () => {
  it('formats years, ISO dates and passes anything else through', () => {
    expect(dateText(-490)).toBe('490 BCE');
    expect(dateText('1969')).toBe('1969 CE');
    expect(dateText('1976-07-02')).toBe('2 Jul 1976 CE');
    expect(dateText('1976-07')).toBe('Jul 1976 CE');
    expect(dateText('-0044-03-15')).toBe('15 Mar 44 BCE');
    expect(dateText('c. 500 BC')).toBe('c. 500 BC');
    expect(dateText(null)).toBeNull();
  });

  it('spans whole years between two bounds', () => {
    expect(spanText('1969', '1976-07-02')).toBe('7 years');
    expect(spanText(-509, -27)).toBe('482 years');
    expect(spanText(10, 10)).toBe('under a year');
    expect(spanText(10, null)).toBeNull();
    expect(numericYear('-0044-03-15')).toBe(-44);
  });

  it('builds the short date line, preferring the display range', () => {
    const d = { temporal_display_range: null, era_label: 'Antiquity' };
    expect(temporalText({ ...d, temporal_start: '-0509', temporal_end: '-0027-01-16' })).toBe(
      '509 BCE – 16 Jan 27 BCE',
    );
    expect(temporalText({ ...d, temporal_start: null, temporal_end: null })).toBe('Antiquity');
    expect(
      temporalText({ ...d, temporal_display_range: 'c. 500 BC', temporal_start: 1, temporal_end: 2 }),
    ).toBe('c. 500 BC');
  });

  it('humanises keys', () => {
    expect(humanise('transcript_run')).toBe('Transcript run');
  });
});

describe('citationRows', () => {
  it('reads the pipeline citation object, linking what it can', () => {
    const rows = citationRows({
      confidence: 1,
      created_by: 'historical-agent-pipeline',
      ohm_feature: 'relation/2745245',
      wikidata_id: 'Q1072362',
      wikidata_url: 'https://www.wikidata.org/wiki/Q1072362',
      empty: null,
    });
    expect(rows).toEqual([
      { label: 'Confidence', value: '1', href: undefined },
      { label: 'Created by', value: 'historical-agent-pipeline', href: undefined },
      {
        label: 'Ohm feature',
        value: 'relation/2745245',
        href: 'https://www.openhistoricalmap.org/relation/2745245',
      },
      {
        label: 'Wikidata url',
        value: 'https://www.wikidata.org/wiki/Q1072362',
        href: 'https://www.wikidata.org/wiki/Q1072362',
      },
    ]);
  });

  it('links a bare wikidata id', () => {
    expect(citationRows({ wikidata_id: 'Q1' })[0].href).toBe('https://www.wikidata.org/wiki/Q1');
  });

  it('handles arrays of strings and objects, strings, and nothing', () => {
    expect(
      citationRows(['https://a.example', { title: 'Herodotus', url: 'https://b.example' }, 'Book II']),
    ).toEqual([
      { label: 'Source 1', value: 'https://a.example', href: 'https://a.example' },
      { label: 'Herodotus', value: 'https://b.example', href: 'https://b.example' },
      { label: 'Source 3', value: 'Book II', href: undefined },
    ]);
    expect(citationRows('Thucydides')).toEqual([
      { label: 'Source', value: 'Thucydides', href: undefined },
    ]);
    expect(citationRows(null)).toEqual([]);
    expect(citationRows([])).toEqual([]);
  });
});

describe('mediaItems', () => {
  it('accepts URLs and {url, caption, type} objects, skipping junk', () => {
    expect(
      mediaItems([
        'https://x.example/a.jpg',
        { url: 'https://x.example/b', caption: 'Map', type: 'image' },
        { url: 'not a url' },
        42,
      ]),
    ).toEqual([
      { url: 'https://x.example/a.jpg', caption: null, isImage: true },
      { url: 'https://x.example/b', caption: 'Map', isImage: true },
    ]);
    expect(mediaItems('https://x.example/doc.pdf')).toEqual([
      { url: 'https://x.example/doc.pdf', caption: null, isImage: false },
    ]);
    expect(mediaItems(null)).toEqual([]);
  });
});

describe('attributeRows', () => {
  it('formats values and skips keys shown elsewhere', () => {
    expect(
      attributeRows({
        capital: 'Persepolis',
        population: 50000,
        is_empire: true,
        languages: ['Old Persian', 'Elamite'],
        date_raw: 'c. 550 BC',
        nothing: null,
        none: [],
        nested: { a: 1 },
      }),
    ).toEqual([
      { key: 'capital', label: 'Capital', value: 'Persepolis' },
      { key: 'population', label: 'Population', value: (50000).toLocaleString() },
      { key: 'is_empire', label: 'Is empire', value: 'Yes' },
      { key: 'languages', label: 'Languages', value: 'Old Persian, Elamite' },
      { key: 'nested', label: 'Nested', value: '{"a":1}' },
    ]);
  });
});
