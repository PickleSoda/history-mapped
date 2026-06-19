import type { EntityGroup } from '@/types/atlas';

export interface SampleSpan {
  id: string;
  label: string;
  group: EntityGroup;
  /** Historical year; negative = BCE. */
  start: number;
  end: number;
  /** Lane (row) index, 0-based. */
  lane: number;
}

/** Number of lanes the sample gantt is laid out across. */
export const SAMPLE_LANES = 6;

/** Placeholder gantt until real entity spans are wired (design §"seam"). */
export const sampleSpans: SampleSpan[] = [
  { id: 'rome-rep', label: 'Roman Republic', group: 'polity', start: -509, end: -27, lane: 0 },
  { id: 'rome-emp', label: 'Roman Empire', group: 'polity', start: -27, end: 476, lane: 0 },
  { id: 'han', label: 'Han Dynasty', group: 'polity', start: -206, end: 220, lane: 1 },
  { id: 'maurya', label: 'Maurya Empire', group: 'polity', start: -322, end: -185, lane: 2 },
  { id: 'silk-road', label: 'Silk Road trade', group: 'economy', start: -130, end: 1453, lane: 3 },
  { id: 'library-alex', label: 'Library of Alexandria', group: 'culture', start: -283, end: 275, lane: 4 },
  { id: 'punic-wars', label: 'Punic Wars', group: 'event', start: -264, end: -146, lane: 5 },
  { id: 'alexandria', label: 'Alexandria founded', group: 'place', start: -331, end: -330, lane: 4 },
  { id: 'gupta', label: 'Gupta Empire', group: 'polity', start: 320, end: 550, lane: 2 },
  { id: 'pax-romana', label: 'Pax Romana', group: 'event', start: -27, end: 180, lane: 5 },
];
