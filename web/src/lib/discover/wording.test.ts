import { describe, expect, it } from 'vitest';
import {
  becauseLine,
  dayKeyLabel,
  inSentence,
  kindWord,
  meanwhileRule,
  onTheMap,
  regionInSentence,
  relationLine,
  relationWords,
  sentenceName,
  storedDayLabel,
  withoutOpeningAside,
  yearReason,
} from './wording';

const event = (name: string) => ({ name, entity_group: 'event' as const });
const article = (entity: Parameters<typeof sentenceName>[0]) => sentenceName(entity).article;

describe('a name inside a sentence', () => {
  it('adds "the" to an event named with an "of / on / at / for" phrase', () => {
    for (const name of [
      'Battle of Hastings',
      'Siege of Vienna',
      'Norman conquest of England',
      'Great Fire of London',
      'Wall Street Crash of 1929',
      '1883 eruption of Krakatoa',
      'March on Rome',
      'Scramble for Africa',
      'Battle of Xi’an',
      'Siege of Jerusalem (1099)',
    ]) {
      expect(article(event(name)), name).toBe('the ');
    }
  });

  it('adds "the" to an event that ends in a noun such as War or Rebellion', () => {
    for (const name of [
      'First Crusade',
      'An Lushan Rebellion',
      'Great Northern War',
      'Second World War',
      'Punic Wars',
      'French Revolution',
      'Meiji Restoration',
      '1755 Lisbon earthquake',
      'First Sino-Japanese War (1894–1895)',
      'Yalta Conference',
      'Nuremberg trials',
      'Easter Rising',
      'Molotov–Ribbentrop Pact',
      '20 July plot',
      'Darien scheme',
    ]) {
      expect(article(event(name)), name).toBe('the ');
    }
  });

  it('adds "the" to such a noun followed by "in" and a place', () => {
    for (const name of [
      'Williamite War in Ireland',
      'War in the Vendée',
      'Barracks bombings in Beirut',
      'Battle in the Bay of Matanzas',
    ]) {
      expect(article(event(name)), name).toBe('the ');
    }
    // Not any name with "in": the word before it must be the event.
    expect(article(event('Martial law in Poland'))).toBe('');
    expect(article(event('Rumble in the Jungle'))).toBe('');
    expect(article(event("Yamankan's rebellion in Pegu"))).toBe('');
  });

  it('leaves alone a name that never takes one, or gives no sign', () => {
    for (const name of [
      'Operation Overlord',
      'Operation Northern Offensive',
      'Hurricane Katrina',
      'World War I',
      'Black Death',
      'Bloody Sunday',
      'Kristallnacht',
      'Reconquista',
      'Vikrama retakes Ujjain',
    ]) {
      expect(article(event(name)), name).toBe('');
    }
  });

  it('never adds one to a name with a possessive', () => {
    for (const name of [
      'Queen Anne’s War',
      "King Philip's War",
      "Shays' Rebellion",
      "Hundred Years' War",
      "Hannibal's crossing of the Alps",
      "Battle of King's Mountain",
    ]) {
      expect(article(event(name)), name).toBe('');
    }
  });

  it('writes a name\'s own article small, outside the name', () => {
    expect(sentenceName(event('The Troubles'))).toEqual({ article: 'the ', name: 'Troubles' });
    expect(sentenceName(event('The Anarchy'))).toEqual({ article: 'the ', name: 'Anarchy' });
    expect(inSentence(event('The Troubles'))).toBe('the Troubles');
    // Not a name that merely starts with those letters.
    expect(sentenceName(event('Theban hegemony'))).toEqual({ article: '', name: 'Theban hegemony' });
  });

  it('is only for events: people, states and places keep their names', () => {
    expect(article({ name: 'Joan of Arc', entity_group: 'polity' })).toBe('');
    expect(article({ name: 'Kingdom of England', entity_group: 'polity' })).toBe('');
    expect(article({ name: 'Frankfurt on the Oder', entity_group: 'place' })).toBe('');
    expect(sentenceName({ name: 'The Gambia', entity_group: 'polity' })).toEqual({ article: '', name: 'The Gambia' });
    expect(inSentence({ name: 'Kingdom of England', entity_group: 'polity' })).toBe('Kingdom of England');
    expect(inSentence(event('Battle of Hastings'))).toBe('the Battle of Hastings');
  });
});

describe('on this day', () => {
  it('says what the day marks in a word, and nothing for an event that happened', () => {
    expect(kindWord('happened')).toBeNull();
    expect(kindWord('began')).toBe('begins');
    expect(kindWord('ended')).toBe('ends');
    expect(kindWord('born')).toBe('born');
    expect(kindWord('died')).toBe('died');
    expect(kindWord('founded')).toBe('founded');
    expect(kindWord('dissolved')).toBe('ends');
  });

  it('leaves the opening aside out of a person\'s summary', () => {
    expect(
      withoutOpeningAside(
        'Selma Ottilia Lovisa Lagerlöf (US also; Swedish: [ˈsɛ̂lːma]; 20 November 1858 – 16 March 1940) was a Swedish writer.',
      ),
    ).toBe('Selma Ottilia Lovisa Lagerlöf was a Swedish writer.');
    // Brackets inside the aside, and punctuation straight after it.
    expect(withoutOpeningAside('Pius VIII (Italian: Pio VIII (born Castiglioni); 1761 – 1830), pope from 1829.')).toBe(
      'Pius VIII, pope from 1829.',
    );
    // Only the first one goes.
    expect(withoutOpeningAside('Ada (1815 – 1852) wrote on the Analytical Engine (1843).')).toBe(
      'Ada wrote on the Analytical Engine (1843).',
    );
  });

  it('returns a summary it cannot safely shorten as it is', () => {
    const late = `${'A long opening sentence that says who this was. '.repeat(3)}(a late aside) follows.`;
    expect(withoutOpeningAside(late)).toBe(late);
    expect(withoutOpeningAside('No aside here.')).toBe('No aside here.');
    expect(withoutOpeningAside('Never closed (Swedish: Selma')).toBe('Never closed (Swedish: Selma');
    expect(withoutOpeningAside('(All of it is an aside)')).toBe('(All of it is an aside)');
    expect(withoutOpeningAside('Name (aside)')).toBe('Name (aside)');
    expect(withoutOpeningAside('')).toBe('');
  });

  it('labels a day key and a stored date', () => {
    expect(dayKeyLabel('2026-11-20')).toBe('20 November');
    expect(dayKeyLabel('2026-03-01')).toBe('1 March');
    expect(storedDayLabel('1815-11-19')).toBe('19 November');
    expect(storedDayLabel('-0753-04-21')).toBe('21 April');
    expect(storedDayLabel('1925-11-20T00:00:00Z')).toBe('20 November');
    expect(storedDayLabel('+1925-01-09T00:00:00Z')).toBe('9 January');
  });

  it('has no day label for a date without a real day', () => {
    expect(storedDayLabel('1815')).toBeNull();
    expect(storedDayLabel('1815-11')).toBeNull();
    expect(storedDayLabel('1815-13-40')).toBeNull();
    expect(storedDayLabel('1815-00-00')).toBeNull();
    expect(storedDayLabel('')).toBeNull();
  });

  it('says why the browse page shows that year', () => {
    const item = (kind: Parameters<typeof yearReason>[0]['kind'], name: string, group: 'event' | 'polity') => ({
      kind,
      name,
      entity_group: group,
    });
    expect(yearReason(item('happened', 'Battle of Vuelta de Obligado', 'event'))).toBe(
      'The year of the Battle of Vuelta de Obligado',
    );
    expect(yearReason(item('began', 'Siege of Vienna', 'event'))).toBe('The year the Siege of Vienna began');
    expect(yearReason(item('ended', 'First Crusade', 'event'))).toBe('The year the First Crusade ended');
    expect(yearReason(item('born', 'Leo Tolstoy', 'polity'))).toBe('The year Leo Tolstoy was born');
    expect(yearReason(item('died', 'Leo Tolstoy', 'polity'))).toBe('The year Leo Tolstoy died');
    expect(yearReason(item('founded', 'Kingdom of Italy', 'polity'))).toBe('The year Kingdom of Italy was founded');
    expect(yearReason(item('dissolved', 'Soviet Union', 'polity'))).toBe('The year Soviet Union ended');
  });
});

describe('meanwhile', () => {
  it('names a region after "in"', () => {
    expect(regionInSentence({ key: 'europe', name: 'Europe' })).toBe('Europe');
    expect(regionInSentence({ key: 'middle-east-north-africa', name: 'Middle East & North Africa' })).toBe(
      'the Middle East & North Africa',
    );
    expect(regionInSentence({ key: 'somewhere-new', name: 'Somewhere New' })).toBe('Somewhere New');
  });

  it('counts what is on the map', () => {
    expect(onTheMap({ polities: 233, events: 42 })).toBe('233 states and 42 events on the map');
    expect(onTheMap({ polities: 1, events: 1 })).toBe('1 state and 1 event on the map');
    expect(onTheMap({ polities: 37, events: 0 })).toBe('37 states on the map');
    expect(onTheMap({ polities: 0, events: 1234 })).toBe('1,234 events on the map');
    expect(onTheMap({ polities: 0, events: 0 })).toBeNull();
  });

  it('says how the rows were chosen', () => {
    expect(meanwhileRule(10)).toBe(
      'Each region: its most notable event within 10 years, and its most written-about state.',
    );
    expect(meanwhileRule(1)).toBe(
      'Each region: its most notable event within 1 year, and its most written-about state.',
    );
  });
});

describe('for you', () => {
  it('names what was opened, up to two', () => {
    expect(becauseLine([])).toBeNull();
    expect(becauseLine(['  '])).toBeNull();
    expect(becauseLine(['Hannibal'])).toBe('Because you opened Hannibal');
    expect(becauseLine(['Hannibal', 'Scipio Africanus'])).toBe('Because you opened Hannibal and Scipio Africanus');
    expect(becauseLine(['Hannibal', 'Scipio Africanus', 'Carthage'])).toBe(
      'Because you opened Hannibal, Scipio Africanus and 1 more',
    );
    expect(becauseLine(['A', 'B', 'C', 'D'], 3)).toBe('Because you opened A, B, C and 1 more');
    expect(becauseLine(['A', 'B', 'C'], 3)).toBe('Because you opened A, B and C');
  });

  it('puts a relationship type in plain words', () => {
    expect(relationWords('victorious_at')).toBe('victorious at');
    expect(relationWords('at_war_with')).toBe('at war with');
    expect(relationWords('ruler')).toBe('ruler');
    expect(relationWords('')).toBeNull();
    expect(relationWords(null)).toBeNull();
  });

  it('reads a relationship in the direction it runs', () => {
    // "Britain, victorious at, Battle of Magdala": the row is the source.
    expect(relationLine('victorious_at', 'Battle of Magdala', false)).toBe('victorious at Battle of Magdala');
    // "Siege of Jhain, commanded by, Jalal ud-Din": the opened entity is the source.
    expect(relationLine('commanded_by', 'Siege of Jhain', true)).toBe('Siege of Jhain: commanded by');
    // No direction given: the two side by side, claiming nothing.
    expect(relationLine('commanded_by', 'Siege of Jhain', null)).toBe('commanded by · via Siege of Jhain');
    expect(relationLine('commanded_by', 'Siege of Jhain', undefined)).toBe('commanded by · via Siege of Jhain');
  });

  it('says what it can with a part missing', () => {
    expect(relationLine('victorious_at', null, false)).toBe('victorious at');
    expect(relationLine('victorious_at', '  ', true)).toBe('victorious at');
    expect(relationLine(null, 'Hannibal', true)).toBe('via Hannibal');
    expect(relationLine('', 'Hannibal', null)).toBe('via Hannibal');
    expect(relationLine(null, null, null)).toBeNull();
  });
});
