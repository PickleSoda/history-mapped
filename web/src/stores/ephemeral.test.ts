import { describe, it, expect, afterEach } from 'vitest';
import { useEphemeralStore } from './ephemeral';

afterEach(() => useEphemeralStore.getState().setTimelineMode('collapsed'));

describe('timelineMode slice', () => {
  it('defaults to collapsed', () => {
    expect(useEphemeralStore.getState().timelineMode).toBe('collapsed');
  });
  it('is updated by setTimelineMode', () => {
    useEphemeralStore.getState().setTimelineMode('transient');
    expect(useEphemeralStore.getState().timelineMode).toBe('transient');
    useEphemeralStore.getState().setTimelineMode('pinned');
    expect(useEphemeralStore.getState().timelineMode).toBe('pinned');
  });
});
