import { describe, expect, it } from 'vitest';
import {
  applyDiff,
  diffStats,
  diffWords,
  listText,
  normaliseList,
  normaliseText,
  tokenize,
} from './text-diff';

const roundTrip = (base: string, proposed: string) => {
  const chunks = diffWords(base, proposed);
  expect(applyDiff(chunks, 'base')).toBe(base);
  expect(applyDiff(chunks, 'proposed')).toBe(proposed);
  return chunks;
};

describe('tokenize', () => {
  it('splits words, whitespace runs and single punctuation', () => {
    expect(tokenize('Rome, founded  753 BC.')).toEqual([
      'Rome', ',', ' ', 'founded', '  ', '753', ' ', 'BC', '.',
    ]);
  });

  it('keeps non-Latin letters and combining marks inside words', () => {
    expect(tokenize('Ἀθῆναι café')).toEqual(['Ἀθῆναι', ' ', 'café']);
  });
});

describe('diffWords', () => {
  it('marks a single word replacement, deletion before insertion', () => {
    const chunks = roundTrip('The Roman Empire fell in 476.', 'The Western Roman Empire fell in 476.');
    expect(chunks).toEqual([
      ['=', 'The '],
      ['+', 'Western '],
      ['=', 'Roman Empire fell in 476.'],
    ]);
  });

  it('orders a replacement as - then +', () => {
    expect(roundTrip('fell in 476', 'fell in 480')).toEqual([
      ['=', 'fell in '],
      ['-', '476'],
      ['+', '480'],
    ]);
  });

  it('diffs punctuation on its own', () => {
    expect(roundTrip('Rome, Italy', 'Rome. Italy')).toEqual([
      ['=', 'Rome'],
      ['-', ','],
      ['+', '.'],
      ['=', ' Italy'],
    ]);
  });

  it('handles empty sides', () => {
    expect(roundTrip('', 'New text')).toEqual([['+', 'New text']]);
    expect(roundTrip('Old text', '')).toEqual([['-', 'Old text']]);
    expect(roundTrip('', '')).toEqual([]);
  });

  it('folds a whitespace island between two changes into one change', () => {
    expect(roundTrip('one two', 'uno dos')).toEqual([
      ['-', 'one two'],
      ['+', 'uno dos'],
    ]);
  });

  it('keeps a non-whitespace equal run between changes', () => {
    expect(roundTrip('a b c', 'x b y')).toEqual([
      ['-', 'a'],
      ['+', 'x'],
      ['=', ' b '],
      ['-', 'c'],
      ['+', 'y'],
    ]);
  });

  it('normalises CRLF before diffing', () => {
    const chunks = diffWords('one\r\ntwo', 'one\ntwo');
    expect(chunks).toEqual([['=', 'one\ntwo']]);
  });

  it('returns a single equal chunk when nothing changed', () => {
    expect(roundTrip('Same words.', 'Same words.')).toEqual([['=', 'Same words.']]);
  });

  it('round-trips multi-line rewrites', () => {
    roundTrip(
      'Line one stays.\nLine two goes away.\nLine three.',
      'Line one stays.\nA brand new line.\nLine three, edited!',
    );
  });

  it('round-trips a large wholesale rewrite (coarse fallback)', () => {
    const base = Array.from({ length: 1800 }, (_, i) => `a${i}`).join(' ');
    const proposed = Array.from({ length: 1800 }, (_, i) => `b${i}`).join(' ');
    roundTrip(base, proposed);
  });
});

describe('diffStats', () => {
  it('counts changed word tokens per side', () => {
    expect(diffStats(diffWords('fell in 476 AD', 'fell in the year 480'))).toEqual({
      added: 3,
      removed: 2,
    });
  });

  it('does not count punctuation-only edits as words', () => {
    expect(diffStats(diffWords('Rome, Italy', 'Rome. Italy'))).toEqual({ added: 0, removed: 0 });
  });
});

describe('normaliseText', () => {
  it('normalises line endings and trims', () => {
    expect(normaliseText('  a\r\nb\r  ')).toBe('a\nb');
  });
});

describe('normaliseList', () => {
  it('trims, drops blanks, dedupes case-insensitively and sorts', () => {
    expect(normaliseList('  Athens \r\n\nathenai\nAthènes\nATHENS\n  \nAthenai')).toBe(
      'athenai\nAthens\nAthènes',
    );
  });

  it('keeps the first spelling of a duplicate', () => {
    expect(normaliseList('Byzantium\nbyzantium')).toBe('Byzantium');
    expect(normaliseList('byzantium\nByzantium')).toBe('byzantium');
  });

  it('sorts by code unit, not locale', () => {
    // 'é' (U+00E9) sorts after 'z' by code unit; localeCompare would not.
    expect(normaliseList('élan\nzeta\nalpha')).toBe('alpha\nzeta\nélan');
  });

  it('is empty for an empty or blank list', () => {
    expect(normaliseList('')).toBe('');
    expect(normaliseList(' \n \r\n')).toBe('');
  });

  it('diffs only real additions and removals once both sides are normalised', () => {
    const base = normaliseList('Rome\nRoma');
    const proposed = normaliseList('Rome\nUrbs\nRoma');
    expect(diffWords(base, proposed)).toEqual([['=', 'Roma\nRome'], ['+', '\nUrbs']]);
  });
});

describe('listText', () => {
  it('orders stored items by code unit so the same duplicate spelling wins', () => {
    // As the server: 'Athens' < 'athens' by code unit.
    expect(listText(['athens', 'Sparta', 'Athens'])).toBe('Athens\nSparta');
  });

  it('trims before ordering, so padding cannot pick the spelling', () => {
    expect(listText([' charles the wise', 'Charles the Wise'])).toBe('Charles the Wise');
  });
});

describe('diffWords byLine', () => {
  it('keeps, adds and removes whole list items', () => {
    const base = 'Charles the Wise\nKarl V';
    const proposed = 'Charles le Sage\nCharles the Wise';
    const chunks = diffWords(base, proposed, true);
    expect(chunks).toEqual([['+', 'Charles le Sage\n'], ['=', 'Charles the Wise'], ['-', '\nKarl V']]);
    expect(applyDiff(chunks, 'base')).toBe(base);
    expect(applyDiff(chunks, 'proposed')).toBe(proposed);
  });

  it.each([
    ['B\nC', 'A\nB\nC'],
    ['A\nB', 'A\nB\nC'],
    ['A\nB\nC', 'A\nC'],
    ['A\nB', ''],
    ['', 'A\nB'],
    ['A\nB', 'C\nD'],
    ['A\nC\nE', 'B\nC\nD\nE\nF'],
  ])('round-trips %j → %j', (base, proposed) => {
    const chunks = diffWords(base, proposed, true);
    expect(applyDiff(chunks, 'base')).toBe(base);
    expect(applyDiff(chunks, 'proposed')).toBe(proposed);
  });
});
