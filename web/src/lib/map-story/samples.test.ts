/**
 * The committed stories (api/resources/map-stories, built by the pipeline)
 * parse without falling back on any enum, and every phase of every step
 * resolves and draws: the web vocabulary keeps up with the pipeline's.
 */
import { describe, expect, it } from 'vitest';
import { MapStoryDocumentSchema } from '@/lib/schemas/map-story';
import { resolveBeatFrames, resolveConditions, resolveFeatureStates, stepBounds, stepPhases } from './geometry';
import { featureCollections, featurePoints, holdCollection, moveCollection, noteCollection, unitCollections } from './layers';

type Json = Record<string, unknown>;

const stories = import.meta.glob<Json>('../../../../api/resources/map-stories/*.json', { eager: true, import: 'default' });
// A checkout without the API's stories has nothing to check.
if (Object.keys(stories).length === 0) it.skip('needs api/resources/map-stories', () => {});

describe.each(Object.keys(stories))('%s', (path) => {
  const raw = stories[path];
  const doc = MapStoryDocumentSchema.parse(raw);

  it('parses every enum and v2 extra as written', () => {
    (raw.steps as Json[]).forEach((rawStep, i) => {
      const step = doc.steps[i];
      expect(step.light ?? null).toBe((rawStep.light as string) ?? null);
      expect(Object.keys(step.features)).toEqual(Object.keys(((rawStep.features ?? rawStep.terrain_state) as Json) ?? {}));
      [rawStep, ...((rawStep.beats as Json[]) ?? [])].forEach((rawPhase, q) => {
        const phase = stepPhases(step)[q];
        expect(phase.moves.map((m) => m.type)).toEqual(((rawPhase.moves as Json[]) ?? []).map((m) => m.type));
        expect(phase.notes.map((n) => n.kind)).toEqual(((rawPhase.notes as Json[]) ?? []).map((n) => n.kind ?? 'label'));
        for (const [uid, pl] of Object.entries((rawPhase.positions as Record<string, Json>) ?? {})) {
          expect(phase.positions[uid]).toEqual(pl);
        }
      });
    });
    expect(doc.alt_sites).toHaveLength(((raw.alt_sites as unknown[]) ?? []).length);
    expect(doc.features).toHaveLength(((raw.features ?? raw.terrain) as unknown[] | undefined)?.length ?? 0);
  });

  it('resolves and draws every phase of every step', () => {
    const phases = resolveBeatFrames(doc);
    const holds = resolveFeatureStates(doc);
    expect(resolveConditions(doc)).toHaveLength(doc.steps.length);
    phases.forEach((frames, i) => {
      const step = doc.steps[i];
      expect(frames).toHaveLength(step.beats.length + 1);
      frames.forEach((frame, q) => {
        const drawn = unitCollections(doc, frame, step.focus);
        // A battle always has formations on the field; a wider story may have only markers or features.
        if (doc.schema < 3) expect(drawn.units.features.length).toBeGreaterThan(0);
        moveCollection(doc, step, frames, q);
        noteCollection(step, q);
      });
      holdCollection(doc, holds[i]);
      const bounds = stepBounds(doc, frames[frames.length - 1], i, featurePoints(featureCollections(doc, holds[i])));
      if (doc.schema < 3 || !step.camera) expect(bounds).not.toBeNull();
    });
  });
});
